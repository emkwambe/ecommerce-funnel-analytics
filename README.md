# E-commerce Funnel Analytics

Where does the view-to-purchase funnel lose the most recoverable revenue, and what should the team test first?

This portfolio project analyzes a real e-commerce event log (view, cart, and purchase events) with a dbt pipeline on DuckDB, a documented metric layer, KPI dashboards, a data discrepancy investigation, and a natural-language-to-SQL agent. It also records how Claude Code was used under a human-in-the-loop workflow (`ai-workflow/`).

**Status:** Sprint 0 (data preflight). No business metrics have been defined yet.

## Data and attribution

Data: "eCommerce behavior data from multi category store" by REES46, collected by the Open CDP project.

- Kaggle dataset page: https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store
- REES46 Marketing Platform: https://rees46.com

This repository publishes aggregates and findings only. It contains no raw data and no row-level extracts. See [docs/data-source.md](docs/data-source.md) for the license and the basis for use.
