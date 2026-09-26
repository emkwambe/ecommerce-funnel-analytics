// Phone-width screenshots with device emulation (390x844, mobile, touch, DPR 2), light and dark.
// Usage: SCREENSHOT_URL=http://localhost:3000 SCREENSHOT_SET=sprint-1 npm run screenshots
// Fails if any page, or any scroll container on it, overflows horizontally at 390 px.
//
// Evidence image policy: full-resolution PNGs go to ai-workflow/evidence/full/<set>/ (gitignored). The
// committed set is WebP at 50% scale, quality 70, in ai-workflow/evidence/<set>/; a pytest check fails
// if any committed evidence image exceeds 300 KB.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { toWebp } from "./webp.mjs";

const base = (process.env.SCREENSHOT_URL || "https://ecommercefunnel-analytics.vercel.app").replace(/\/$/, "");
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const set = process.env.SCREENSHOT_SET || "sprint-1";
const fullDir = process.env.SCREENSHOT_OUT || join(repoRoot, "ai-workflow", "evidence", "full", set);
const webpDir = join(repoRoot, "ai-workflow", "evidence", set);
const writeWebp = process.env.SCREENSHOT_WEBP !== "0";
const pages = (process.env.SCREENSHOT_PAGES || "/,/funnel,/data-quality,/data,/metrics,/how-its-built,/investigations,/investigations/revenue-figures,/investigations/later-purchases").split(",");
const themes = ["light", "dark"];

mkdirSync(fullDir, { recursive: true });
if (writeWebp) mkdirSync(webpDir, { recursive: true });
const browser = await chromium.launch();
let failures = 0;

for (const theme of themes) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    colorScheme: theme,
  });
  const page = await context.newPage();
  for (const path of pages) {
    const res = await page.goto(base + path, { waitUntil: "networkidle" });
    const status = res?.status() ?? 0;
    const { scrollWidth, clientWidth, innerOverflow } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      // Scroll containers (e.g. table wrappers) whose content is wider than the box.
      innerOverflow: [...document.querySelectorAll(".overflow-x-auto")].filter((el) => el.scrollWidth > el.clientWidth + 1)
        .length,
    }));
    const stem = `${path === "/" ? "home" : path.slice(1)}-390-${theme}`;
    const png = join(fullDir, `${stem}.png`);
    await page.screenshot({ path: png, fullPage: true });
    if (writeWebp) await toWebp(png, join(webpDir, `${stem}.webp`));
    const ok = status === 200 && scrollWidth <= clientWidth && innerOverflow === 0;
    if (!ok) failures++;
    console.log(
      `${ok ? "PASS" : "FAIL"}  ${path} [${theme}] status ${status}, scrollWidth ${scrollWidth} / clientWidth ${clientWidth}, clipped scroll boxes ${innerOverflow} -> ${stem}`,
    );
  }
  await context.close();
}

await browser.close();
process.exit(failures ? 1 : 0);
