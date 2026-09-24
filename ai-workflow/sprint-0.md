# E-commerce Funnel Analytics — Sprint 0: Data Preflight

Read `C:\Dev\ecommerce-funnel-analytics\CLAUDE.md` in full first. It is binding, and the metric lock (rule 3) applies for this entire sprint.

**Sprint goal:** establish what the data actually is before any plan or metric is written. By the end we know:

- whether the license lets us publish derived work;
- the exact schema;
- the real data-quality problems, with counts;
- the questions a human must decide before metrics are defined.

**No business metric is computed in this sprint.** This sprint is also exempt from the deploy rule, because there is nothing to deploy yet. Sprint 1 ships the first site.

Stop and report at any failure, license restriction, or ambiguity.

## Step 0 — Environment preflight

Run and report:

- `py -0p`, `node -v`, `vercel --version`, `gh auth status`;
- free disk space on C:;
- total RAM;
- whether the Kaggle CLI is installed and has credentials at `%USERPROFILE%\.kaggle\kaggle.json`.

The candidate data is several GB of CSV. If there is less than 25 GB free disk, stop and report.

If the Kaggle CLI is missing, install it in the project venv, created in Step 2. If credentials are missing, stop and tell me exactly what to do. Never ask me to paste a token into chat.

## Step 1 — Repo and conventions commit

1. `git init` at `C:\Dev\ecommerce-funnel-analytics`.
2. Create a `.gitignore` covering `analysis\.venv\`, `data\`, `__pycache__\`, `.pytest_cache\`, `web\node_modules\`, `web\.next\`, `web\.vercel\`, `pipeline\target\`, `pipeline\logs\`, `.env*`, and full-resolution evidence images.
3. Commit `CLAUDE.md`, `ai-workflow\sprint-0.md`, `ai-workflow\correction-log.md`, and `.gitignore` with the message `project conventions and data preflight spec (before data access)`.
4. Create the public GitHub repo `emkwambe/ecommerce-funnel-analytics` and push, so the commit has a public timestamp.
5. Report the SHA.

## Step 2 — Python scaffold

Create `analysis\` as the installable package `funnel`, with pinned `requirements.txt` containing duckdb, pandas, pyarrow, pytest, and kaggle. Create the venv and install, per CLAUDE.md.

## Step 3 — License check (before download)

The candidate dataset is "eCommerce behavior data from multi category store" on Kaggle, published by REES46. Find its exact Kaggle slug. Do not assume one.

1. Read the dataset page's license field and any terms or attribution requirements stated by the publisher.
2. Record the exact license name, the attribution text required, and the URLs in a draft of `docs\data-source.md`.
3. **Stop and report before downloading if the license:**
   - prohibits redistribution of derived aggregates;
   - prohibits public or portfolio use;
   - is unclear.

   Publishing aggregated marts and findings, with no raw data, is the intended use.

## Step 4 — Ingest

Implement `funnel\ingest.py` (`python -m funnel.ingest`):

1. Download only the **October 2019** file into `data\raw\`. Scope is one month; do not download other months.
2. Compute its SHA-256.
3. Convert it to Parquet with DuckDB, written to `data\parquet\`, preserving all columns and types. Report the conversion's row count against the CSV's row count; they must match.
4. Generate `docs\data-source.md` containing:
   - source;
   - slug and URL;
   - license and attribution;
   - retrieval UTC date;
   - file name, size, SHA-256;
   - row count;
   - column list with DuckDB-inferred types.

## Step 5 — Structural profile (the metric lock applies)

Implement `funnel\profile.py` (`python -m funnel.profile`), using DuckDB SQL over the Parquet. It generates `docs\data-profile.md` and `ai-workflow\evidence\sprint-0\profile.json` (with a manifest). Profile structure and quality only:

1. **Schema and completeness:** every column's type, null count, and null share, and distinct counts for id-like columns.
2. **Time:** min and max `event_time`, its timezone representation, and whether any events fall outside October 2019.
3. **Event types:** the distinct levels and their overall counts only. No rates, and no breakdown by anything.
4. **Duplicates:**
   - exact duplicate rows;
   - near-duplicates on (user_session, product_id, event_type, event_time);
   - near-duplicates on (user_session, product_id, event_type) within the same second.
5. **Price:** count of zero, negative, and null prices; distribution quantiles (min, p1, p50, p99, max); and whether the same product_id appears at different prices, with a count.
6. **Categories and brands:** null or empty share of `category_code` and `brand`, and whether `category_id` maps to more than one `category_code`, with a count.
7. **Sessions and users:**
   - null `user_session` count;
   - sessions spanning more than one user_id;
   - distribution of events per session (quantiles);
   - sessions longer than 24 hours.
8. **Ordering anomalies:**
   - purchase events whose session has no view of that product;
   - purchase events with no cart event for that product in the session;
   - cart events with no prior view.

   Report counts only.
9. **Order reconstruction:**
   - Confirm whether any order or transaction ID exists.
   - If not, report how many sessions contain multiple purchase events, and how many identical (session, product) purchase pairs occur.

   This determines how "order" and "revenue" can be defined, which is a human decision for Sprint 1.

Every figure in `data-profile.md` is written by code. End the document with a code-generated **"Decisions needed before metric definitions"** section. It lists each anomaly with its count, the choices it forces, and the plausible options. For example: how to deduplicate; whether zero-price purchases count as revenue; how to define an order without an order ID; how to treat purchases with no view; how to handle missing categories. Present the options neutrally; I decide.

## Step 6 — Tests

In `analysis\tests\`:

- For each profile check, verify it on a small synthetic event log with known anomalies. Every anomaly type must be detected with the exact expected count.
- Assert that the Parquet row count equals the CSV row count.
- **Metric-lock guard:** assert that `profile.json` contains no rate, ratio, or revenue sum grouped by category, brand, product, time bucket, or user segment. Test the guard by deliberately injecting a leak into a copy and confirming it's caught.

## Step 7 — Evidence and push

Write `ai-workflow\sprint-0-verification.md` containing:

- the preflight output;
- the license finding;
- the ingest hash and row counts;
- the pytest summary line;
- a summary of the profile's anomaly counts, taken from `profile.json`.

Update the correction log. If no errors were caught, add an explicit "none caught" entry that lists the checks that were run.

Commit, gated on pytest's own exit code, and push.

## Definition of Done

- [ ] Preflight reported; disk and credentials confirmed
- [ ] Conventions commit made and pushed before any data access; SHA reported
- [ ] License recorded, and it permits publishing derived aggregates (or the sprint stopped)
- [ ] October 2019 file ingested; SHA-256 recorded; Parquet row count equals CSV row count
- [ ] `data-profile.md` and `profile.json` generated by code, with every structural check present
- [ ] "Decisions needed" section lists every anomaly with counts and options
- [ ] All tests pass, including the metric-lock guard and its injected-leak check
- [ ] Verification file and correction log complete; pushed

## Final report format

End the sprint with a report containing:

- the commits made, with SHAs;
- the license, verbatim, with its URL;
- the dataset hash and row count;
- the pytest summary line;
- the "Decisions needed" list, verbatim;
- anything surprising.
