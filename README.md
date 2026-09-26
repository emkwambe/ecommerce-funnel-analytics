# E-commerce Funnel Analytics

**Live site: https://ecommercefunnel-analytics.vercel.app**

Where in the view-to-purchase funnel do sessions most often end with no observed purchase, which categories hold the most carted value with no observed purchase in the session, and what should the team test first?

This portfolio project analyzes a real e-commerce event log (view, cart, and purchase events) with a dbt pipeline on DuckDB, a documented metric layer, KPI dashboards, a data discrepancy investigation, and a natural-language-to-SQL agent. It also records how Claude Code was used under a human-in-the-loop workflow (`ai-workflow/`). It is the second project in a series, after [email-experiment-readout](https://github.com/emkwambe/email-experiment-readout).

**Status:** Sprint 1 (pipeline and definitions). The metric contract is committed, the dbt pipeline is built and tested, the headline metrics are independently verified, and the site describes the funnel. Recommendations on what to test first come in a later sprint.

## Data and attribution

Data: "eCommerce behavior data from multi category store" by REES46, collected by the Open CDP project. This project uses the October 2019 file.

- Kaggle dataset page: https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store
- REES46 Marketing Platform: https://rees46.com

This repository publishes aggregates and findings only. It contains no raw data and no row-level extracts. See [docs/data-source.md](docs/data-source.md) for the license and the basis for use.

## What is on the site

| Page | What it shows |
|---|---|
| [Overview](https://ecommercefunnel-analytics.vercel.app/) | Headline KPIs for the month, each with its definition, and daily trends by UTC day of session start |
| [Funnel](https://ecommercefunnel-analytics.vercel.app/funnel) | The session funnel, purchase paths, and categories by carted value with no observed purchase in the session |
| [Data quality](https://ecommercefunnel-analytics.vercel.app/data-quality) | Every data-quality metric with its basis, and the long-session sensitivity |
| [Data](https://ecommercefunnel-analytics.vercel.app/data) | Source, contents, the structural profile's findings, decisions D1 to D10, and the reconciliation from raw rows to orders |
| [Metrics](https://ecommercefunnel-analytics.vercel.app/metrics) | The metric contract, rendered from `docs/metrics.md` |
| [How it's built](https://ecommercefunnel-analytics.vercel.app/how-its-built) | The git timeline and the correction log, by the numbers |

Every number on the site is read from JSON exports written by code, each carrying a provenance manifest (git commit, dataset SHA-256, UTC timestamp, script).

## How Claude Code was used

- **Planning in chat.** The business question, sprint briefs (`ai-workflow/sprint-*.md`), and the metric contract (`docs/metrics.md`) were drafted with Claude and committed as files. The human owner decided every question the data or the contract left open, in writing.
- **Execution in Claude Code.** Claude Code carried out each sprint brief under the rules in [CLAUDE.md](CLAUDE.md): no hand-typed numbers, a metric lock until the contract was committed, a memory gate before heavy runs, and gated commits. It stopped and asked whenever a spec was ambiguous or a check failed.
- **Verification.** The dbt pipeline carries schema, reconciliation, and tie tests, and every build must run all expected tests. `funnel.verify` recomputes the headline metrics from the raw file without dbt and must match exactly. Guard tests enforce the naming rules and the no-row-level-data rule.
- **The record.** Every error that a test, check, or review caught is in [ai-workflow/correction-log.md](ai-workflow/correction-log.md), committed with its fix. Verification evidence is in [ai-workflow/](ai-workflow/), including [sprint-1-verification.md](ai-workflow/sprint-1-verification.md).

## Reproduce

Requirements: Python 3.12, Node 22, a Kaggle API token in the `KAGGLE_API_TOKEN` environment variable, and about 25 GB of free disk. Heavy stages need at least 3 GB of available memory and halt otherwise. Commands use absolute paths (Windows PowerShell).

```powershell
# Python environment
py -3.12 -m venv C:\Dev\ecommerce-funnel-analytics\analysis\.venv
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m pip install -r C:\Dev\ecommerce-funnel-analytics\analysis\requirements.txt
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m pip install -e C:\Dev\ecommerce-funnel-analytics\analysis

# Data: download the October 2019 file, hash it, convert to Parquet (a provenance event; run rarely)
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m funnel.ingest

# Structural profile, dbt pipeline, independent verification, exports
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m funnel.profile
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m funnel.build
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m funnel.verify
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m funnel.export

# Tests
C:\Dev\ecommerce-funnel-analytics\analysis\.venv\Scripts\python.exe -m pytest C:\Dev\ecommerce-funnel-analytics\analysis\tests -q

# Site
npm --prefix C:\Dev\ecommerce-funnel-analytics\web install
npm --prefix C:\Dev\ecommerce-funnel-analytics\web run build
npm --prefix C:\Dev\ecommerce-funnel-analytics\web run smoke
```

Every stage after ingest halts if the raw file's SHA-256 differs from the value in `docs/data-source.md`.
