# E-commerce Funnel Analytics — Sprint 1: Metric Contract, dbt Pipeline, First Site

Read these before doing anything:

- `C:\Dev\ecommerce-funnel-analytics\CLAUDE.md`
- `docs\metrics.md`
- `docs\data-profile.md`
- `ai-workflow\sprint-0-verification.md`

**Sprint goal:** commit the metric contract, build a tested dbt pipeline that implements it exactly, verify the headline numbers independently, and ship the first live site with KPI, funnel, and data-quality pages.

Stop and report at any failed check, any metric the contract doesn't define clearly, or any ambiguity.

## Step 0 — Preflight and Sprint 0 follow-ups

1. **Preflight.** Run `py -0p`, `node -v`, `vercel --version`, `gh auth status`. Report free disk and **free RAM**. If free RAM is below 3 GB before a heavy run, stop and tell me, so I can close programs.
2. **Delete the Kaggle zip.** Remove the zip file in `C:\Dev\ecommerce-funnel-analytics\data\raw\` using its literal filename. Keep the CSV and the Parquet.
3. **UTC check in repo code.** Move the UTC round-trip check into `funnel.ingest` as a function with a test on synthetic data. Record its result on the real file in `docs\data-source.md` without re-downloading.
4. **Business question wording.** Update the business question in CLAUDE.md prose to: *"Where in the view-to-purchase funnel do sessions most often end with no observed purchase, which categories hold the most carted value with no observed purchase in the session, and what should the team test first?"*
5. **Clean manifests.**
   - Commit all the above.
   - Rerun `funnel.profile` and the verification script from the clean tree, in the foreground as far as the harness allows.
   - Confirm the manifests show `git_worktree_dirty: false` and the committed SHA.
   - Commit the regenerated evidence.

## Step 1 — Commit the metric contract

Commit `docs\metrics.md` exactly as provided, with the message `metric contract (before any business metric is computed)`. Report the SHA.

This lifts the metric lock. Update CLAUDE.md rule 3 to say business metrics may now be computed, **only as defined in `docs\metrics.md`**.

## Step 2 — Naming-rule test

Add `analysis\tests\test_naming_rules.py`. It fails if any file under `web\`, `docs\` (excluding the naming-rules section of `metrics.md`), or any JSON export contains:

- a term prohibited by metrics.md Section 1, rule 3;
- "carts" or "unique carts" used as a count label.

Test the test by injecting a prohibited term into a copy and confirming it fails.

## Step 3 — dbt pipeline (dbt-duckdb)

Create `pipeline\` as a dbt project on DuckDB, reading the Parquet from `data\parquet\` and writing to `data\warehouse.duckdb`. Use the same memory settings as `funnel\common.py`: a 4 GB limit, 4 threads, insertion order off, and spill to `data\duckdb_tmp`. Pin the dbt-core and dbt-duckdb versions.

**Staging**

- `stg_events`: typed columns. Carry one row per deduplicated event, using exact-duplicate removal per D1, and keep the removed count available. Add `is_zero_price`. Add `category_top`, the text before the first dot, with "unknown" for missing values. Add `category_code_label` and `brand_label`, each with "unknown" for missing values.

**Intermediate**

- `int_sessions`: one row per valid session per metrics.md Section 3, with:
  - flags for view, cart, and purchase;
  - `is_long_session` (longer than 24 hours);
  - event counts.
- `int_session_products`: one row per (session, product), with:
  - carted and purchased flags;
  - the latest cart price;
  - the earliest purchase price;
  - the purchase event count.
- `int_purchases`: one row per deduplicated purchase event in a valid session, with its path classification per Section 5.

**Marts**

- `mart_kpis_daily`: Section 4 and Section 6 metrics by UTC day, plus month totals.
- `mart_funnel_category`: the category funnel at (session, category_top) grain per Section 9, plus carted value with no observed purchase in the session, per category.
- `mart_purchase_paths`: Section 5 metrics.
- `mart_data_quality`: every Section 10 metric, including the long-session sensitivity for each headline rate.

**Tests**

- Unique and not_null on every grain key.
- accepted_values on event types and path labels.
- **Reconciliation tests** as dbt singular tests:
  - raw rows − removed duplicates = `stg_events` rows;
  - mart revenue = the sum of purchase prices in `int_purchases`;
  - month-total sessions in `mart_kpis_daily` = the `int_sessions` count;
  - revenue split by path sums to total revenue;
  - carted pairs with no observed purchase + carted pairs with a purchase = carted pairs.

Document every model and column in dbt YAML, citing the metrics.md section each implements.

## Step 4 — Independent verification

In `analysis\funnel\verify.py`, recompute these directly from the Parquet with separately written DuckDB SQL, not referencing dbt models:

- valid sessions;
- orders;
- revenue, primary and secondary;
- session purchase rate;
- view-to-cart session rate;
- cart-session purchase rate;
- revenue share by path;
- carted value with no observed purchase in the session.

Assert that each matches the marts exactly, as integers or to 1e-9 for rates. Also verify the data-quality counts match the Sprint 0 profile where they overlap (duplicates removed, zero-price events, null-session events, multi-user sessions).

## Step 5 — Exports

`python -m funnel.export` writes these to `web\public\data\`, each with a manifest:

- `kpis.json`
- `funnel_category.json`
- `purchase_paths.json`
- `data_quality.json`
- `metrics_index.json` (metric name, definition text, and metrics.md section, generated by parsing metrics.md)

## Step 6 — Web (first site)

Build a Next.js 15 site in `web\`: TypeScript strict, Tailwind, light/dark theme, and responsive down to 390px. Pages:

- **`/` Overview.** The business question, then headline KPIs for the month: sessions, orders, revenue, AOV, revenue per session, session purchase rate. Each KPI has a definition tooltip from `metrics_index.json`. Include a UTC daily trend chart. Show a status badge "Sprint 1 · pipeline and definitions".
- **`/funnel`.** The session funnel using the Section 6 display labels exactly. Show the purchase-path split with revenue shares, and a category funnel table with carted value with no observed purchase in the session. The unknown-category share is visible on the page. Descriptive only: no recommendations yet.
- **`/data-quality`.** Every Section 10 metric, including the long-session sensitivity table.
- **`/metrics`.** Renders `docs\metrics.md`. Add a drift test so the web copy always equals the committed file.
- **`/how-its-built`.** The Claude Code workflow, links to `ai-workflow\`, and correction-log statistics generated by code.

**Footer on every page:**

- "An analytics case study built with Claude Code by Eddy Mkwambe"
- the two required attribution links (the Kaggle dataset page and the REES46 Marketing Platform), with a test that checks both.

All numbers come from JSON, and every interpretive sentence cites its fields. Charts are inline SVG.

## Step 7 — Smoke, deploy, evidence

`web\scripts\smoke.mjs` checks:

- all five pages return 200;
- every JSON export loads;
- manifest hashes match `docs\data-source.md`;
- the footer attribution links are present on `/`.

Then:

1. Deploy with `vercel deploy --prod --cwd C:\Dev\ecommerce-funnel-analytics\web`, and run `npm --prefix C:\Dev\ecommerce-funnel-analytics\web run smoke` against production.
2. Take 390px screenshots in both themes, committing only compressed WebP files (300 KB limit).
3. Write `ai-workflow\sprint-1-verification.md`.
4. Update the correction log.
5. Update the README with the live URL, the business question, and the attribution.
6. Set the repo website field.
7. Gate every commit on pytest's own exit code and `dbt build` success, and push.

## Definition of Done

- [ ] Step 0 complete; clean manifests committed
- [ ] Metric contract committed before any business metric; SHA reported
- [ ] Naming-rule test passes, and its injected-term check fails as expected
- [ ] `dbt build` passes: all models, schema tests, and reconciliation tests
- [ ] Independent verification matches the marts exactly
- [ ] Five pages live, 390px-verified, with labels exactly per metrics.md
- [ ] Attribution footer present and tested; smoke passes against production
- [ ] Verification file, correction log, and README complete; pushed

## Final report format

End the sprint with a report containing:

- the commits made, with SHAs, including the metric-contract commit;
- the `dbt build` summary;
- the pytest summary line;
- smoke output;
- the headline KPIs as read from `kpis.json`;
- the path revenue split;
- the three categories with the most carted value with no observed purchase in the session, with each category's unknown-inclusive context;
- the long-session sensitivity results;
- correction-log entries added;
- anything surprising or needing a decision.
