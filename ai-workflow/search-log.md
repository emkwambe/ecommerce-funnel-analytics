# Search Log — E-commerce Funnel Analytics (append-only)

Every hypothesis, model, specification, feature set, subgroup, and test tried, **including those that failed or were dropped**. A result can't be published without its history here.

Template: verified-analytics-project v2.1. Created in Sprint 2 Step 0 (2026-09-26). Sprints 0 and 1 computed only the fixed metrics defined in `docs/metrics.md`, with no search over specifications, so this log starts with Sprint 2.

| # | Date | What was tried | Pre-specified or exploratory | Data evaluated on | Result | Kept? | Commit |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-26 | A: revenue difference and repeat purchase events, total (A items 1–2) | pre-specified (H2, H3) | hand-counted synthetic log only (`test_investigation_a.py`, scratch dbt dry run) | code check, not a finding: both paths match the hand counts | yes | this commit |
| 2 | 2026-09-26 | A: breakdown by time since the previous purchase event (0 s / 1–59 s / ≥ 60 s) | pre-specified | synthetic only | code check | yes | this commit |
| 3 | 2026-09-26 | A: breakdown by price compared with the pair's first purchase price | pre-specified | synthetic only | code check | yes | this commit |
| 4 | 2026-09-26 | A: breakdown by top-level category | pre-specified | synthetic only | code check | yes | this commit |
| 5 | 2026-09-26 | A: breakdown by purchase events in the pair (2 / 3 / 4 or more) | pre-specified | synthetic only | code check | yes | this commit |
| 6 | 2026-09-26 | A: time × price two-way table | pre-specified | synthetic only | code check | yes | this commit |
| 7 | 2026-09-26 | A: concentration diagnostic (top-10-pair share per group) | pre-specified | synthetic only | code check | yes | this commit |
| 8 | 2026-09-26 | A: threshold sensitivity at 0 s, 1 s, 5 s, 10 s, 30 s, 60 s, 5 min, 30 min, 1 h | pre-specified | synthetic only | code check | yes | this commit |
| 9 | 2026-09-26 | A-S1: exact duplicate rows by event type and group size | pre-specified | synthetic only | code check | yes | this commit |
| 10 | 2026-09-26 | A-S2: cart events with no view at or before them, raw basis to contract basis | pre-specified | synthetic only | code check | yes | this commit |

| 11 | 2026-09-26 | Rows 1–10 run once on the real data: full `dbt build` at `e335f67` (PASS=149), `funnel.verify` (83 of 83 A checks match), export at `7e3d506` | pre-specified | October 2019 event log (dataset SHA-256 in `docs/data-source.md`), all valid sessions | all ten cuts computed; values in `web/public/data/investigation_revenue_gap.json`. No cut was dropped, re-specified, or selected | all reported | `0da0e2e` |
| 12 | 2026-09-26 | A timing, D1: per-second distribution of time since the pair's previous purchase event, 1–300 s and > 300 s | **exploratory** (owner decision H4) | real data, repeat purchase events | reported to the owner only; not published, values not committed | diagnostic only | — |
| 13 | 2026-09-26 | A timing, D2: price and top-level category of repeat purchase events in the 31–60 s band | **exploratory** | real data | reported to the owner only | diagnostic only | — |
| 14 | 2026-09-26 | A timing, D3: share of the 31–60 s band held by the top 1% of users and of sessions, with the same statistic over all repeat purchase events as a reference | **exploratory** | real data | reported to the owner only | diagnostic only | — |
| 15 | 2026-09-26 | A timing, D4: the band's share by UTC day and by UTC hour | **exploratory** | real data | reported to the owner only | diagnostic only | — |
| 16 | 2026-09-26 | A timing, D5: per-second gaps between consecutive same-type events of the same session and product (views, cart events; purchases as a cross-check) | **exploratory** | real data, deduplicated events in valid sessions | first run had a bug (correction log); rerun reported to the owner only | diagnostic only | — |
| 17 | 2026-09-26 | B1: carted pairs, 7-day window (cutoff 2019-10-24), count and value shares with user-level cluster bootstrap intervals | pre-specified (H2, H3), primary | hand-counted synthetic log only (`test_investigation_b.py`, scratch dbt build of the B models) | code check, not a finding: both paths match the hand counts | yes | this commit |
| 18 | 2026-09-26 | B2 and B3: 3-day (cutoff 2019-10-28) and 14-day (cutoff 2019-10-17) windows | pre-specified, sensitivity | synthetic only | code check | yes | this commit |
| 19 | 2026-09-26 | B4: Kaplan–Meier over all carted pairs with no purchase in the session, count and value-weighted, bands; R3 agreement rule | pre-specified, R3 | synthetic only | code check | yes | this commit |
| 20 | 2026-09-26 | B5: comparison baseline (viewed-only pairs, four conditions with cart → view), 7 days; stop rule | pre-specified, control | synthetic only | code check | yes | this commit |
| 21 | 2026-09-26 | B6: one pair per (user, product); B7: excluding users above the 99.9th percentile of events; B8: excluding cart sessions over 24 hours | pre-specified, sensitivities | synthetic only | code check | yes | this commit |
| 22 | 2026-09-26 | B9: `user_id` checks; item 16 diagnostics (overlap, within 1 hour, top 0.1% users, sessions per user) | pre-specified, data check and diagnostics | synthetic only | code check | yes | this commit |
| 23 | 2026-09-26 | Seed stability: B1 intervals and the KM 7-day interval with seeds 20260927–29 | pre-specified (H3-D5) | synthetic only | code check | yes | this commit |
| 24 | 2026-09-26 | Rows 17–23 on the real data. Run 1: full `dbt build` at `1512d76` (PASS=191). Run 2: `funnel.verify` at `07920cb` (113 of 113 match; a first attempt was stopped by the harness under system memory pressure before writing anything). Run 3: `funnel.later_purchases` at `a013aff` | pre-specified | October 2019 event log | all B specifications computed; the R3 agreement stop rule **fired**, and the cohort diagnostic ran as pre-specified (B-D6). Identity and baseline rules did not fire. Values in `ai-workflow/evidence/sprint-2/later_purchases.json` | reported to the owner in an escalation brief; not published | this commit |

Rows 1–10 fix every analysis A cut before the real data is used. Rows 17–23 do the same for analysis B, including its cohort diagnostic, which runs only if the R3 agreement rule fails (owner decision B-D6). Rows 12–16 are exploratory: they generate hypotheses, not findings, and nothing from them is published without a Changes entry. Their code is `analysis/explore/a_timing_diagnostic.py`, committed on the owner's instruction. Its results matched the reported run exactly when rerun to a path outside the repository. Its outputs are never committed: the script refuses in-repo paths, `.gitignore` excludes everything but Python source in that folder, and `test_explore_outputs.py` enforces it. Each real-data run is logged as a new row that references these numbers. A is descriptive, and it tests no hypothesis.

**Running totals:** hypotheses 0 tested (A is descriptive; row 16 compares shapes without a test); specifications 10 pre-specified + 5 exploratory diagnostics (rows 12–16, two runs of row 16); uses of the evaluation data 3 (row 11; the diagnostic run twice). Analysis B: 7 pre-specified specifications plus KM, seed stability, and the conditional cohort diagnostic; 1 use of the evaluation data (row 24). These feed the false-discovery gate.
