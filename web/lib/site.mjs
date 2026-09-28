// The one place the repository URL is set (owner decision, v1.1.6). The site header, the "full history" link on
// /how-its-built, the commit and file links, and the smoke test all read it from here. Plain JS so the smoke test
// (web/scripts/smoke.mjs) can import it too.
export const REPO_URL = "https://github.com/emkwambe/ecommerce-funnel-analytics";
export const COMMITS_URL = `${REPO_URL}/commits/main`;
