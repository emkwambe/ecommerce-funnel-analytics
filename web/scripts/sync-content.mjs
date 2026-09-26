// Copies the metric contract from docs/ into web/content/ before every build, so /metrics renders
// the committed document rather than a hand-maintained duplicate. On Vercel only web/ is uploaded,
// so the copy made by the last local build is used there; a Python test
// (analysis/tests/test_web.py) asserts the copy is byte-identical to docs/metrics.md.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(webRoot, "..", "docs", "metrics.md");
const target = join(webRoot, "content", "metrics.md");

if (existsSync(source)) {
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
  console.log(`sync-content: copied ${source} -> ${target}`);
} else if (existsSync(target)) {
  console.log("sync-content: docs/ not present (remote build); using committed web/content copy");
} else {
  console.error("sync-content: neither docs/metrics.md nor web/content/metrics.md exists");
  process.exit(1);
}
