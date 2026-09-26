# Tool Inventory — E-commerce Funnel Analytics

This is what the command center can use, when to prefer each tool, and when **not** to use it. Read it at the start of every session. Verify versions with preflight commands; never assume them.

Template: trio-sprint-workflow v2.3 (`assets/templates/tools.md`). Created in Sprint 2 Step 0 (2026-09-26); versions below were verified by the Sprint 2 preflight on that date.

## Evidence hierarchy (stronger → weaker)

| Claim about… | Strongest evidence | Weaker substitute (never use as final) |
|---|---|---|
| External software or APIs | Current primary docs + verified behavior | Model memory, blog posts |
| The data | A query against the actual data | Data documentation, publisher descriptions |
| Code behavior | An executed test or run | Reading the code, reasoning |
| Production state | A production smoke test | A local build |
| A result's validity | Independent reproduction (separate implementation or alternative method) | A rerun of the same path |
| Domain meaning | Primary sources, standards | Secondary summaries |

Observed behavior outranks remembered behavior. When sources conflict, follow the contradiction protocol.

## Tools: selection guide

| Tool | Appropriate use | Inappropriate substitute for | Evidence produced |
|---|---|---|---|
| Web fetch / search (Chat) | Current official docs, primary sources, name checks | Inspecting our own repository or data | Cited documentation |
| Repository inspection (Code) | What our code and configuration actually contain | Knowing what the code *does* at runtime | File contents and diffs |
| pytest (Code, CI) | Behavior of `funnel` code, guards (naming, row-level data, env drift, exports, web copy) | Pipeline correctness on the real data (CI has no raw data) | Test output and pytest's own exit code |
| DuckDB SQL (Code) | Facts about the data; anything over the raw file (too large for pandas) | Meaning or causality | Counts and values with the query |
| `funnel.build` (dbt build and tests) | Pipeline correctness, reconciliation; records tests run against tests expected | Independent verification (it's the same path) | `ai-workflow/evidence/*/dbt_build_runs.json` |
| `funnel.verify` (independent verifier) | R2: headline numbers recomputed from the Parquet file without dbt | R3 (it's the same method, reimplemented) | `verify.json`, match per check |
| Production smoke (`npm --prefix web run smoke`) | Deployed state: pages, exports, manifest hashes, attribution | — | Pass/fail per check |
| Screenshots (`npm --prefix web run screenshots`) | Rendered pages at 390 px and desktop, both themes; page overflow and clipped scroll boxes | Reading a text rendering of a page | WebP evidence (300 KB limit), pass/fail per page |
| CI (GitHub Actions, from Sprint 2) | Gates that run independently of the local agent: pytest on committed exports and fixtures, web lint and build, link check | Heavy data runs (no raw data or dbt in CI) | CI logs |
| Copilot review | A second-model code review | Validating statistics or domain meaning | Review comments (to evaluate, not obey). **Not available to this account, as observed 2026-09-26** (Sprint 2 Step 1, PR #1): `gh pr edit 1 --add-reviewer "@copilot"` and the REST call `POST /pulls/1/requested_reviewers` with `copilot-pull-request-reviewer[bot]` both returned success, but no reviewer was recorded and the PR timeline shows no `review_requested` event. The first project (`email-experiment-readout`) has no PRs, so there is no earlier evidence. PRs proceed on CI plus the owner's review; recheck if the owner enables a Copilot plan |
| LLM judgment (Chat or Code) | Planning, framing questions, drafting | Anything that can be computed, queried, or tested | Proposals only; never evidence |

## Environment

### Claude Chat (command center)
| Capability | Available | Notes |
|---|---|---|
| Web search and fetch | not verified from Claude Code | The owner confirms |
| File creation / sandbox execution | not verified from Claude Code | |
| Connectors | not verified from Claude Code | |
| Skills | trio-sprint-workflow v2.3, verified-analytics-project v2.1 | Also loaded in Claude Code |

### Claude Code (executor)
| Tool | Version (verified 2026-09-26) | Purpose |
|---|---|---|
| Shell | PowerShell 7 (primary); Git Bash available | Absolute paths only, never `cd` first. Arguments beginning with `/` go through PowerShell or with `MSYS_NO_PATHCONV=1` (correction log, v1.0.1) |
| Python | 3.12.10 (`analysis\.venv`) | `funnel` package |
| dbt-core / dbt-duckdb | 1.12.5 / 1.11.0 | Pipeline (`pipeline\`), dbt threads 1 |
| DuckDB | 1.5.5 | 2 GB memory limit, 4 threads, insertion order off, spill to `data\duckdb_tmp` |
| pytest | 9.1.1 | Commit gate (own exit code) |
| Node / npm | 22.18.0 / 11.7.0 | Web build, smoke, screenshots |
| Next.js | 15.5.26 | Site (`web\`) |
| gh | 2.92.0 | Account `emkwambe`; scopes gist, read:org, repo, workflow |
| Vercel CLI | 58.4.4 | Production deploys (`vercel deploy --prod --cwd C:\Dev\ecommerce-funnel-analytics\web`) |
| git | 2.53.0.windows.2 | Never rewrite history, never force-push |

### External systems
| System | Role | Notes |
|---|---|---|
| GitHub (`emkwambe/ecommerce-funnel-analytics`, public) | Source, CI (status checks `python-tests`, `web-build`, `docs-checks`; GitGuardian also reports on PRs) | Copilot review not available (see above). Tier: Governed from Sprint 2 (branch → PR → CI → Copilot review if available → owner merge). Tags: `v1.0.0` (annotated, retroactive, at `a96f7e0`; created 2026-09-26) and `v1.0.1` (at `b7f0044`). Branch protection on `main` from 2026-09-26: PR required, the three CI checks required and up to date, rules enforced for admins, no force pushes, no deletion |
| Vercel (project `ecommerce-funnel-analytics`, id `prj_0lDt1FQ5rZPbWrx2KFzrPk7HEFjG`) | Production | Domain: https://ecommercefunnel-analytics.vercel.app, a project domain (verified via the project domains API, not a one-off alias). No git link: deploys happen only through the CLI, so merges and PRs do not deploy. Vercel builds on Node 24.x; local builds use Node 22.18.0 |
| Kaggle: "eCommerce behavior data from multi category store" (REES46, Open CDP), October 2019 file | Data source | License field `copyright-authors`; owner's basis for use and the dataset SHA-256 in `docs/data-source.md`. Aggregates only; no raw or row-level data committed. Token: `KAGGLE_API_TOKEN` (see `.env.example`) |

### Machine constraints
RAM 15.78 GB total; available-memory gate 3 GB (`\Memory\Available MBytes`, checked by `python -m funnel.ramcheck`); DuckDB limit 2 GB (owner override, `ai-workflow/sprint-1-verification.md`); free disk 71.7 GB on C: at the Sprint 2 preflight; available memory 3,255 MB at that preflight. Known memory hogs: browsers (Chrome) and Docker's WSL VM; the owner closes them before heavy runs. A full clean `dbt build` takes about 17–23 minutes and spills about 11 GB. `funnel.verify` takes 11–15 minutes and spills 16–21 GiB since Sprint 2 (`ai-workflow/sprint-2-verification.md`). The spill needs that much free disk in `data/duckdb_tmp` on top of the data files.

**Claude Code harness (observed in Sprint 2):** it stops an idle background command when the system runs critically low on memory. This stopped one `funnel.verify` run before it wrote anything, and orphaned spill files had to be deleted by literal path. Since then, heavy runs are started in the background with a Monitor watching their stages, available memory, and terminal state, so the session is never idle during a run. A foreground command is capped at 10 minutes, too short for `build` or `verify`. The harness can be told not to stop background commands under memory pressure by starting Claude Code with `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`; it was not set in Sprint 2.

**Statistics:** numpy (bundled with pandas) for the analysis B bootstrap and Kaplan–Meier (`funnel.later_purchases`); DuckDB SQL for the independent R2 recomputation, including a SQL product-limit Kaplan–Meier.
