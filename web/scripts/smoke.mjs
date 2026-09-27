// Smoke test for the site. Usage: npm run smoke (production) or SMOKE_URL=http://localhost:3000 npm run smoke.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const base = (process.env.SMOKE_URL || "https://ecommercefunnel-analytics.vercel.app").replace(/\/$/, "");
const dataSourceDoc = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "data-source.md");
const documentedSha = readFileSync(dataSourceDoc, "utf-8").match(/^- \*\*SHA-256:\*\* `([0-9a-f]{64})`/m)?.[1];

const PAGES = ["/", "/funnel", "/data-quality", "/data", "/metrics", "/how-its-built", "/investigations",
  "/investigations/revenue-figures", "/investigations/later-purchases", "/questions"];
const EXPORTS = [
  "kpis.json",
  "funnel_category.json",
  "purchase_paths.json",
  "data_quality.json",
  "metrics_index.json",
  "data_story.json",
  "workflow.json",
  "investigation_revenue_gap.json",
  "investigation_later_purchases.json",
  "closing.json",
];
// Closing (owner decision, 2026-09-27): the committed closing export decides what / and /questions must show.
const closing = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "public", "data", "closing.json"), "utf-8"));
const question1 = closing.questions.find((q) => q.start_here);
// Render {figure} tokens from the export, then compare the text up to the first character HTML may escape.
const rendered = (s) => s.replace(/\{([a-z_]+)\}/g, (_, k) => closing.figures[k].formatted);
const plainPrefix = (s) => rendered(s).split(/["'&<>]/)[0].trim();
const ATTRIBUTION = [
  "https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store",
  "https://rees46.com",
];

const results = [];
const check = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

console.log(`Smoke test against ${base}`);
check("docs/data-source.md records a dataset SHA-256", Boolean(documentedSha), documentedSha?.slice(0, 12));

for (const path of PAGES) {
  try {
    const res = await fetch(base + path, { redirect: "follow" });
    check(`GET ${path} returns 200`, res.status === 200, `status ${res.status}`);
  } catch (e) {
    check(`GET ${path} returns 200`, false, String(e));
  }
}

for (const name of EXPORTS) {
  try {
    const res = await fetch(`${base}/data/${name}`);
    const body = await res.json();
    const sha = body?.manifest?.dataset_sha256;
    check(`${name} loads`, res.status === 200, `status ${res.status}`);
    check(`${name} manifest dataset SHA-256 matches docs/data-source.md`, Boolean(documentedSha) && sha === documentedSha,
      `${sha?.slice(0, 12)}…`);
  } catch (e) {
    check(`${name} loads`, false, String(e));
  }
}

try {
  const html = await (await fetch(`${base}/`)).text();
  for (const url of ATTRIBUTION) {
    check(`footer attribution link on / : ${url}`, html.includes(`href="${url}"`));
  }
} catch (e) {
  check("footer attribution links on /", false, String(e));
}

try {
  const home = await (await fetch(`${base}/`)).text();
  check("/ shows \"Project status: closed\"", home.includes("Project status: closed"));
  check("/ links prominently to /questions", home.includes('href="/questions"'));
  for (const finding of closing.findings) {
    check(`/ shows headline finding ${finding.id}`, home.includes(plainPrefix(finding.text)), plainPrefix(finding.text).slice(0, 40));
  }
  const questions = await (await fetch(`${base}/questions`)).text();
  check("/questions marks question 1 \"Start here\"", questions.includes("Start here") && questions.includes(plainPrefix(question1.question)));
  check(`/questions shows all ${closing.questions.length} questions`,
    closing.questions.every((q) => questions.includes(plainPrefix(q.question))));
  check("/questions has a Sources line", questions.includes("Sources:"));
} catch (e) {
  check("closing content on / and /questions", false, String(e));
}

const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
