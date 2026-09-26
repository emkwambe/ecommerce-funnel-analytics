// Smoke test for the site. Usage: npm run smoke (production) or SMOKE_URL=http://localhost:3000 npm run smoke.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const base = (process.env.SMOKE_URL || "https://ecommercefunnel-analytics.vercel.app").replace(/\/$/, "");
const dataSourceDoc = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "data-source.md");
const documentedSha = readFileSync(dataSourceDoc, "utf-8").match(/^- \*\*SHA-256:\*\* `([0-9a-f]{64})`/m)?.[1];

const PAGES = ["/", "/funnel", "/data-quality", "/data", "/metrics", "/how-its-built"];
const EXPORTS = [
  "kpis.json",
  "funnel_category.json",
  "purchase_paths.json",
  "data_quality.json",
  "metrics_index.json",
  "data_story.json",
  "workflow.json",
];
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

const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
