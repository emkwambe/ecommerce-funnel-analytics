# Sprint 2 — Final report

**Sprint:** Governed tier, discrepancy investigation, purchases in later sessions (`ai-workflow/sprint-2.md`).
**Run under:** trio-sprint-workflow v2.3, verified-analytics-project v2.1.
**Date:** 2026-09-26. **Releases:** v1.1.0 (`243c8c7`) and v1.1.1 (`c153a16`, live).
**Evidence file:** `ai-workflow/sprint-2-verification.md`. Its top part is the owner-decision record; its lower part is generated from saved evidence by `python -m funnel.verification_sprint2`. Every figure below is quoted from that file or from command output shown in the session. None is typed from memory or added by hand.

## Summary

The project moved to the Governed tier and ran every change after Step 0 through ten owner-merged pull requests, with CI on each. Two investigations are published at `/investigations`, each approved as a method (H2) and defined in the metric contract (H3) before it was computed.

**Analysis A** explains the two revenue figures. The difference between revenue and revenue with repeat purchase events collapsed is exactly the value of the purchase events after the first of the same product in a session. The difference is located by price, timing thresholds, pair size, and category. The data cannot say whether those events are extra units or repeated logging, and the page says so.

**Analysis B** measures how much carted value with no observed purchase in the session was followed by a purchase of the same product by the same user in a later session within 7 days. It is scoped to cart sessions starting October 1–24, 2019 UTC, the sessions with full follow-up. Its planned method check (Kaplan–Meier against the fixed window) did not agree. The analysis stopped, as pre-committed. The owner chose to disclose the disagreement and report its source, a lower follow-up rate in late-October cart sessions, as a finding in its own right.

An independent recomputation, written separately from the pipeline, matched every published count, value, and share, and the Kaplan–Meier curve at 3, 7, 14, and 30 days. B's main 7-day figures were recomputed a second time by a different method. The intervals come from one bootstrap implementation, rerun with three other seeds. The owner signed off all thirteen new claim rows (C3–C15) on the live pages (H9).

## Definition of Done

| Item | Status | Evidence |
|---|---|---|
| Governed tier active: CI green, branch protection on (H6), Copilot status recorded; every change after Step 0 merged by the owner through a PR (H8) | done | Branch protection read back (H6 row); Copilot not available (`tools.md`); PRs #1–#10 merged by `emkwambe`, with CI on each |
| Method-selection records approved (H2); Changes entry approved and committed before computation (H3) | done | `method-selection/A-revenue-gap.md`, `B-later-purchases.md`; Changes entry in `ac825a5` (PR #3) before any Sprint 2 run |
| A: decomposition reconciles exactly to the gap; R2 matches; secondary cases reconcile; claim ceiling on the page | done | dbt `assert_revenue_gap_decomposition_reconciles` and others; verify A checks all match; ceiling in section 1 of the page |
| B: censoring-safe estimate, sensitivity windows, R2 match, R3 agreement reported, comparison baseline reported, `user_id` reliability reported, adversarial review recorded | done | R3 **did not agree**: disclosed and escalated (owner decision H4); `adversarial-review-B.md` |
| Search log complete, including unreported runs; claim ledger rows for every new published claim | done | `search-log.md` rows 1–25 (5 exploratory, unpublished); claim rows C3–C15 |
| Correctness level stated for each claim; no open **critical** uncertainty | done | Ledger column "Correctness level"; register: U1 and U2 are open and material, U3 is resolved |
| Documentation cadence: `.env.example` with drift test, CHANGELOG, README, `tools.md`, verification file; drift checks pass | done, with one lag (see Open items) | `test_env_drift.py`; CHANGELOG 1.1.0 and 1.1.1; link check passes |
| Deployed; production smoke passes; tagged v1.1.0; H9 recorded | done (and v1.1.1) | smoke `30/30 checks passed` for both releases; tags pushed after the smoke test; H9 in the ledger |

**Correctness levels established:** implementation correct (tests, reconciliation, R2) and empirically valid as descriptions of these populations. No causal validity is claimed, and none was sought. Practical usefulness is for Sprint 3 to judge.

## Pull requests (all merged by the owner)

```
#1  6e0e959  Sprint 2 Step 1: Governed-tier setup (CI, PR template)
#2  76467d3  Sprint 2 Step 2: method-selection records A and B (H2)
#3  ac825a5  Sprint 2 Step 3: metrics.md Changes entry for investigations A and B (H3)
#4  7249dd6  Sprint 2 Step 4: analysis A (revenue difference), R2, claim rows C3-C7
#5  a091952  Sprint 2 Step 5: analysis B (later purchases), R2/R3, owner decision H4, claim rows C8-C15
#6  cb3d76d  Sprint 2 Step 6: /investigations pages (A and B)
#7  243c8c7  Sprint 2 Step 7: release v1.1.0 (documentation cadence, verification file)
#8  d2f17de  Sprint 2 Step 7 evidence: v1.1.0 deployed, smoke 30/30, screenshots 18/18, tag
#9  c153a16  Sprint 2 Step 7: exact verification wording on the investigation pages (before H9)
#10 46bd249  v1.1.1 records: CHANGELOG entry, deploy and tag, H8 for PR #9
```

Step 0 was the last direct commit to `main` (`03c1eed`). The full commit list is in the generated section of `sprint-2-verification.md`.

## Runs (verbatim)

```
dbt build (e335f67, analysis A): Done. PASS=149 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=149
  Tests run 134 of 134 expected (models built: 15); 3.75 GB available; 1365.4 s; peak spill 10.55 GiB
dbt build (1512d76, analysis B): Done. PASS=191 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=191
  Tests run 170 of 170 expected (models built: 21); 5.06 GB available; 1252.7 s; peak spill 10.5 GiB
funnel.verify (7bc7bb5, latest): Elapsed: 858.7 s; peak spill: 23016341504 bytes (21.44 GiB); all_match=True
  152 of 152 checks: 83 analysis A, 45 analysis B, and the rest from Sprint 1
funnel.later_purchases (a013aff): Elapsed: 540.3 s; peak spill: 0 bytes (0.0 GiB);
  stop rules fired: ['R3 agreement: the B1 7-day count share lies inside the all-pairs KM 7-day 95% interval']
pytest: 174 passed (pytest_exit_code=0)
CI on main at 46bd249: success  python-tests=success  web-build=success  docs-checks=success
Production smoke (v1.1.0 and v1.1.1): Smoke test against https://ecommercefunnel-analytics.vercel.app ... 30/30 checks passed
Production screenshots (v1.1.0), 390 px, light and dark: PASS 18, FAIL 0
```

One verify run was stopped by the Claude Code harness under system memory pressure before it wrote anything (Docker had been restarted). It was rerun with Docker closed and monitored throughout.

## Analysis A — the two revenue figures

From `investigation_revenue_gap.json` (claim rows C3–C7):

```
revenue 229,932,953.94 | collapsed 211,426,365.64 | difference 18,506,588.30 | repeat events 52,401 | pairs 41,340
price:  same as the first purchase event 99.27% | different 0.73%
pair:   2 events 62.88% | 3 events 19.85% | 4 or more 17.27%
share of the difference within T: 0 s 0.00% | 1 s 0.09% | 5 s 0.18% | 10 s 0.36% | 30 s 1.68% | 60 s 24.45% | 5 min 88.85% | 30 min 98.49% | 1 h 99.20%
category: electronics 81.81% | unknown 7.65% | appliances 4.48% | computers 4.33% | ...
A-S1: exact duplicate rows removed, by type and group size, sum to the D1 figure (cart, view, purchase)
A-S2: raw-basis cart events with no view at or before them 4,655 -> published 4,145; difference 510, all rows removed as exact duplicates; remainder 0
```

The same-second group is empty: identical duplicate rows are removed first (D1), which the Sprint 0 reconciliation establishes. Timing is published through the cumulative thresholds only. The 60 s bin edge splits a large mass, so the 1–59 s against 1 minute or more split is not published (owner decision H4 for A). An exploratory per-second diagnostic (search log rows 12–16, script in `analysis/explore/`, outputs never committed) was reported to the owner only. It listed competing explanations without ranking them.

## Analysis B — later purchases

From `investigation_later_purchases.json` (claim rows C8–C15). Shares are count [95% CI] and value [95% CI]:

```
B1 7-day,  sessions Oct 1–24:  13.99% [13.81, 14.16] (36,786 of 263,018) | value 13.40% [13.14, 13.66]
B2 3-day,  sessions Oct 1–28:  12.14% [11.98, 12.29] | 11.52%
B3 14-day, sessions Oct 1–17:  16.23% [16.00, 16.46] | 15.65%
B5 viewed-only (comparison):    1.38% [1.34, 1.41]
B6 one pair per user and product 11.91% | B7 excluding the most active users 13.83% | B8 excluding long sessions 14.00%
Kaplan–Meier, all October:     1 d 10.01% | 3 d 12.21% | 7 d 13.81% [13.64, 13.97] | 14 d 15.10% | 30 d 16.29%
Cohort: sessions after Oct 24, KM 7-day 12.52% [12.18, 12.88] against 13.99% [13.81, 14.16]; the intervals do not overlap
Followed pairs first purchased within 1 hour of the latest cart event: 37.9% (disclosed; may reflect technical session splits)
user_id checks: 0 missing, 0 sessions with more than one user_id, 100% usable
Seed stability (3 other seeds): each bound moves by up to 0.0098%
```

**Stop rules.** The identity rule did not fire. The comparison-baseline rule did not fire. **The R3 agreement rule fired.** The escalation brief (`ai-workflow/escalations/2026-09-26-B-R3-agreement.md`) showed the following:
- The Kaplan–Meier estimate on the matched cohort reproduces B1 to about 1e-13, so the two implementations agree on the same population.
- The disagreement comes from pooling a later cohort with a lower follow-up rate.

Owner decision H4 chose option A with refinements:
- scope every B1 claim to its population;
- report the cohort difference as a finding;
- never apply the value share to any other total, with a guard test;
- disclose the one-hour share.

## Adversarial review (B)

`ai-workflow/adversarial-review-B.md`. The outcomes:
- **Identity linking:** holds within sessions; untestable across sessions, stated as a limitation.
- **Censoring:** the fixed windows are safe; R3 disagreed and was disclosed.
- **Bot-like users:** B7 stays close to B1, and dominance (1.9%) is under the 10% limit.
- **Multiple carts of one product:** B6 is lower and is published beside B1.
- **Technical session splits:** disclosed (the one-hour share).
- **Household purchases:** unobservable, stated as a limitation.
- **Long sessions:** unchanged (B8).
- **Causal reading:** refused; the comparison with viewed-only products is worded descriptively.
- **Reproducibility:** R2 matched everything.

All claims were kept, scoped.

## Claim-ledger rows

C3–C15 in `ai-workflow/claim-ledger.md`, all at "shows", each with its evidence fields, assumptions, validation, reproduction level, correctness level, remaining uncertainty, and adversarial outcome. There is a false-discovery gate for A and for B. **H9:** the owner signed off all thirteen on 2026-09-26, on both pages, on desktop and at 390 px, including the corrected verification wording.

## Owner decisions recorded

Every decision is dated, marked owner-decided, and tied to its artifact in `ai-workflow/sprint-2-verification.md`:
- H1 framing;
- H6 branch protection and the retroactive v1.0.0 tag;
- H2 (A as written; B with edits to B-D1 and B-D6);
- H3 (with edits to D1, D2, D3, and D5);
- H3-D3 extensions (the phrase list, and narrowing `prove`);
- H4 twice (the exploratory timing diagnostic for A; option A for B's R3);
- H4 for the release link (option (b));
- the pasted-block standing rule;
- H8 for PRs #1–#10;
- the v1.1.0 and v1.1.1 releases;
- the owner's pre-H9 review (the verification wording and the 28,152 figure);
- H9 for C3–C15.

## Correction log

21 Sprint 2 entries (counted by code): 20 by Claude Code and 1 from the owner's own specification. By how they were caught: 11 by Claude Code's own review, 5 by the test or commit gate, 3 by the owner's review, and 2 by the screenshot or smoke check. The full list, with each entry's origin and how it was caught, is in the generated section of the verification file. The ones that mattered most for the published claims:
- the later-purchases page overstated its independent recomputation (caught by the owner before H9; fixed in v1.1.1);
- a ledger row claimed an R2 that did not exist yet (the R2 was built rather than the row softened);
- a hand-added total in a session report, which never reached the repository;
- the export's bare DuckDB connection;
- the 390 px overflow from long field paths.

## Open uncertainties

- **U1 (material, open, bounded):** whether repeat purchase events are units or repeated logging. It cannot be settled from this file; the claim ceiling states that.
- **U2 (material, open):** cross-session identity of `user_id`. Within-session identity is verified; cross-device, cross-account, and household purchases cannot be observed, which is stated on the page.
- **U3:** resolved by owner decision H4.

No open critical item.

## Open items needing a decision

1. **The live "How it's built" page lags the correction log.** `workflow.json` was last exported at `ed7c7e4` (Step 6). It holds 40 entries against 47 in the log (counted by code), so seven Sprint 2 entries are not on the site. The first is "Long field paths in Sources lines widened the investigation pages at 390 px". Refreshing it needs an export, a PR, a deploy, and a tag (v1.1.2). **Decision:** refresh now, or at the start of Sprint 3?
2. **One correction-log entry is filed under the wrong "how caught" category.** The README link error was caught by the CI link check, but the classifier (`CAUGHT_RULES` in `funnel/export.py`) has no CI category, so it counts as "Claude Code's own review". **Decision:** add a "CI check" category (a small code change, ideally together with item 1)?
3. **Local branches** `sprint-2/governed-setup`, `method-selection`, `metrics-changes`, `analysis-a`, `analysis-b`, `site`, `release`, `v110-evidence`, `verification-wording`, `v111-records`, and `h9-signoff` remain on this machine. Their work is merged. Deleting them, and their remote copies, is the owner's call.
