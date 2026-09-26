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

Rows 1–10 fix every analysis A cut before the real data is used. Each real-data run is logged as a new row that references these numbers. A is descriptive, and it tests no hypothesis.

**Running totals:** hypotheses 0; specifications 10 (analysis A, all pre-specified); uses of the evaluation data 0. These feed the false-discovery gate.
