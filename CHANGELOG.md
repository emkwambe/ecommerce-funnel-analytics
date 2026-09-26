# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

Entries up to v1.0.1 were reconstructed in Sprint 2 from the git history. Figures are not repeated here; the live site and the verification files carry them.

## [Unreleased]

### Added
- `ai-workflow/tools.md` (tool inventory and machine constraints), `ai-workflow/uncertainty-register.md`, `ai-workflow/search-log.md`, and `ai-workflow/method-selection/`.
- `.env.example` listing every environment variable the code reads (names and descriptions only), guarded by an env-drift test.
- This changelog.
- CI (`.github/workflows/ci.yml`): pytest on committed exports and synthetic fixtures, web lint and build, and a link check of the README, changelog, and docs. A pull request template.
- Method-selection records for the Sprint 2 investigations: A (the two revenue figures) and B (carted products purchased in a later session).
- `docs/metrics.md` Changes entry (2026-09-26) defining every Sprint 2 investigation quantity, approved by the owner before any was computed.
- Wording guard test (`analysis/tests/test_wording_guard.py`) on the investigation pages, the metric contract and its `/metrics` copy, and the README.

### Fixed
- `.env.example` is committed: the `.env*` ignore rule had also matched it (correction log, Sprint 2 Step 0).

### Changed
- The README's "How Claude Code was used" section points to where the owner's decisions are recorded.
- Delivery tier: Governed from Sprint 2 (branch, PR, CI, owner merge).

## [1.0.1] — 2026-09-26

Tag `v1.0.1` (commit `b7f0044`).

### Added
- Two session-level purchase-path counts and the count of sessions with an observed cart event and an observed purchase of no carted product (`docs/metrics.md` Changes, 2026-09-26, third entry).
- The funnel page's purchase step split by path, and the three-way partition of sessions with an observed cart event.
- A "What the data shows" section on the home page, with two descriptive findings, each citing its export fields.
- `ai-workflow/claim-ledger.md`, with owner sign-off (H9) of both findings.

### Changed
- Exports regenerated from a clean tree; independent verification extended to the new counts.

## [1.0.0] — 2026-09-26

Sprint 1 release at commit `a96f7e0` (production deploy evidence, verification file, README). No tag was created at the time. The annotated tag `v1.0.0` was added retroactively on 2026-09-26, during Sprint 2, by the project owner's decision (`ai-workflow/sprint-2-verification.md`).

### Added
- The metric contract, `docs/metrics.md`, committed before any business metric was computed (`8d4093f`), and its Changes entries.
- The dbt pipeline on DuckDB: staging, intermediate, and mart models with schema, reconciliation, and tie tests, behind the memory and dataset-hash gates (`funnel.build`).
- Independent verification of the headline metrics from the Parquet file without dbt (`funnel.verify`).
- JSON exports with provenance manifests (`funnel.export`).
- The Next.js site: overview, funnel, data quality, data, metrics, and how it's built, with the attribution footer.
- Guard tests: naming rules, no row-level data, metrics-page drift, footer attribution, build test coverage.
- Production smoke test and 390 px screenshot checks.

### Changed
- DuckDB memory limit set to 2 GB after owner review; the memory gate reads available memory.

## Sprint 0 — 2026-09-24 (unversioned)

### Added
- Ingest with provenance (`docs/data-source.md`), a structural profile under the metric lock (`docs/data-profile.md`), and the correction log.
