# Sprint 2 verification

Started in Sprint 2 Step 1 to record owner decisions as they are made. Evidence sections (dbt, verify, smoke, analyses A and B) are added in Step 7.

## Owner decisions

Every decision below was made by the project owner (Eddy Mkwambe). Claude Code carried out the actions and recorded the evidence.

| Date | Checkpoint | Decision (owner-decided) | Artifact / evidence |
|---|---|---|---|
| 2026-09-26 | H1 | Sprint 2 framing approved as written in `ai-workflow/sprint-2.md`, including the Sprint 2/3/4 split (recommendations, size-adjusted rankings, Tableau, and the agent deferred to Sprints 3–4). | `ai-workflow/sprint-2.md` (committed in `03c1eed`) |
| 2026-09-26 | H6 | Branch protection on `main` approved as proposed, applied by Claude Code on the owner's instruction: PR required (0 approvals: the owner cannot approve their own PR); required status checks `python-tests`, `web-build`, `docs-checks`; branches up to date before merging; enforced for admins; no force pushes; no deletion. | GitHub branch protection API, read back after applying: `{"checks":["python-tests","web-build","docs-checks"],"deletions":false,"enforce_admins":true,"force_push":false,"pr_required":true,"strict":true}` |
| 2026-09-26 | — (release record) | The `CHANGELOG.md` v1.0.0 entry for the Sprint 1 release at `a96f7e0` is accepted. An annotated retroactive tag `v1.0.0` is created at `a96f7e0` with the message "Retroactive tag for the Sprint 1 release (a96f7e0), created 2026-09-26 during Sprint 2; v1.0.1 followed at b7f0044", and pushed. | `git ls-remote --tags origin`: `refs/tags/v1.0.0` → tag object `47bc571`, peeled to `a96f7e0`. The CHANGELOG v1.0.0 entry and `ai-workflow/tools.md` were updated to name the tag |
| 2026-09-26 | H8 | PR #1 (Sprint 2 Step 1, Governed-tier setup) merged by the owner. | PR #1: state `MERGED`, merged by `emkwambe` at 2026-09-26T10:15:34Z, merge commit `6e0e959`. CI on `main` at `6e0e959`: `python-tests`, `web-build`, `docs-checks` all success |
| 2026-09-26 | H2 | Method selection for A approved as written: A-D1 earliest-price baseline, A-D2 bins 0 s / 1–59 s / ≥ 60 s, A-D3 decomposition table plus threshold sensitivity (label rule and mixture model rejected), A-D4 cases A-S1 and A-S2 (A-S1v dropped), A-D5 claim ceiling. | `ai-workflow/method-selection/A-revenue-gap.md`, "Owner decisions" |
| 2026-09-26 | H2 | Method selection for B approved, with two owner edits. **B-D1:** a later purchase must be in a different valid session of the same user that starts after the cart session starts, **and** its event time must be strictly after the pair's latest cart event, within the window. The owner confirmed this conjunctive reading when asked; cutoffs stay anchored on cart-session start; the overlapping-session diagnostic stays. **B-D6:** if the fixed-window 7-day estimate falls outside the all-pairs KM 95% interval at 7 days, stop and escalate with a cohort diagnostic (KM on pairs from sessions starting by 2019-10-24 versus after), treating neither method as wrong. B-D2 to B-D5, B-D7, and B-D8 approved as recommended. | `ai-workflow/method-selection/B-later-purchases.md`, "Owner decisions" |
| 2026-09-26 | H8 | PR #2 (Sprint 2 Step 2, method-selection records) merged by the owner. | PR #2: state `MERGED`, merged by `emkwambe` at 2026-09-26T10:38:46Z, merge commit `76467d3`, head `db200ba`. CI on `main` at `76467d3` (run 36236413647, push): `python-tests`, `web-build`, `docs-checks` all success |
| 2026-09-26 | H3 | The Changes entry "Sprint 2 investigations: the two revenue figures (A) and later purchases of carted products (B)" approved with edits, before any quantity it defines was computed. **H3-D1** (approved, with an edit): the comparison baseline applies all four later-purchase conditions with only "cart" replaced by "view", and its cutoff and window anchor on the view session's start. **H3-D2** (approved, on a condition): no separate "not followed" figure; the eligible-pair and followed-pair counts are published alongside each share. **H3-D3** (edited): the phrase list is kept in test code, not in the docs, and applies to `/investigations`, the `/metrics` copy, `docs/metrics.md` (outside Section 1), and `README.md`. **H3-D4** (approved): claim tiers at most "shows" for A and B; never "establishes" a mechanism or a cause. **H3-D5** (edited): seed 20260926; a cluster bootstrap at the `user_id` level; a seed-stability check on seeds 20260927, 20260928, and 20260929, reported in this file. | `docs/metrics.md`, Changes; the diff of the revised draft was shown to the owner before commit; `analysis/tests/test_wording_guard.py` |
| 2026-09-26 | — (provenance rule) | Standing rule: a pasted block with no surrounding text is the owner's decision. The owner also confirmed that the pasted H3 message was their decision, and the records stand as written. | Owner message, 2026-09-26 |
| 2026-09-26 | H8 | PR #3 (Sprint 2 Step 3, the Changes entry) merged by the owner, after review of `test_export.py` and `test_wording_guard.py` (approved, with the fixes below). | PR #3: state `MERGED`, merged by `emkwambe` at 2026-09-26T10:47:22Z, merge commit `ac825a5`, head `7a73028`. CI on `main` at `ac825a5` (run 36236842093, push): `python-tests`, `web-build`, `docs-checks` all success |
| 2026-09-26 | H3-D3 (act-and-notify extension) | Wording guard hardened before Step 4 computes anything. (1) The investigations surface skips with a stated reason until a page exists, then must find at least one file, and it also scans the exported files those pages render from. (2) Boundary injections must change the text before findings are checked. (3) New phrases "due to", `impact\w*`, "effect of", `prove\w*`, `demonstrat\w*`, each with a negative test; a match in existing guarded text is reported to the owner, not resolved by rephrasing or dropping a term. | `analysis/tests/test_wording_guard.py`; correction log |
| 2026-09-26 | H3-D3 | `prove\w*` matched "provenance" in `README.md` (lines 31 and 57); Claude Code stopped and reported it. Owner chose option (a): narrow the term to `prove\|proves\|proved\|proven\|proving`, and add "provenance", "improve", and "approve" to the legitimate-wording assertion so a future widening fails. README unchanged. | `analysis/tests/test_wording_guard.py`; correction log |
| 2026-09-26 | H4 | Analysis A slow-down (the 60 s bin edge splits a large mass of repeat purchase events): owner chose (b), then (a). (b) is an exploratory diagnostic: the per-second distribution from 1 to 300 s; price and category in the 31–60 s band; the share of the band held by the top 1% of users and of sessions; the band's share by UTC day and by UTC hour; and a comparison baseline of per-second gaps between consecutive same-type events (views, cart events) of the same session and product. Competing explanations are listed with their predictions, **unranked**. **Scope, decided by the owner:** exploratory only, logged as exploratory, reported to the owner only, and not published. This is an explicit exception to CLAUDE.md rule 3 for unpublished diagnostics; any publication needs a Changes entry. The script and outputs stay outside the public repo. | Search log rows 12–16; the owner's instruction; the diagnostic report in the session |
| 2026-09-26 | H8 | PR #4 (Sprint 2 Step 4, analysis A) merged by the owner. The Step 5 branch `sprint-2/analysis-b`, which had been stacked on it, then merged `main` (`358d590`; no rebase) and targets `main`. | PR #4: state `MERGED`, merged by `emkwambe` at 2026-09-26T16:40:43Z, merge commit `7249dd6`, head `febe6fe`. CI on `main` at `7249dd6` (run 36256311867): success |
| 2026-09-26 | H4 | **Analysis B, the R3 agreement stop rule** (escalation brief `ai-workflow/escalations/2026-09-26-B-R3-agreement.md`): the owner chose **option A**, with three refinements. **(1)** Every B1 claim is scoped to its population, "carted products from sessions starting October 1–24, 2019 UTC". The late-October cohort difference (KM 7-day for sessions after the cutoff against B1) is reported as a finding in its own right on the page and in the ledger. U3 is resolved by this decision. **(2)** No page or ledger row may apply the B1 value share to the total carted value with no observed purchase; a wording test fails on any such extrapolation. **(3)** The page discloses the share of followed pairs whose first later purchase is within one hour of the latest cart event, which may reflect technical session splits rather than return visits. Any further breakdown is exploratory, search-log only, and unpublished. B claims stay at "shows", scoped as above. The B5 comparison is stated descriptively, not causally. | The owner's decision message; `ai-workflow/uncertainty-register.md` (U3 resolved); claim ledger (Step 5) |
| 2026-09-26 | H8 | PR #5 (Sprint 2 Step 5, analysis B) merged by the owner via `gh`. An earlier report of the merge came before it had happened; Claude Code's check found the PR still open and paused Step 6 until the merge. | PR #5: state `MERGED`, merged by `emkwambe` at 2026-09-26T17:22:06Z, merge commit `a091952`, head `8a11207`. CI on `main` at `a091952` (run 36258777784): `python-tests`, `web-build`, `docs-checks` all success |
| 2026-09-26 | Owner review (not H9) | The owner reviewed claim-ledger rows C8–C15 before merging PR #5 and found them correctly scoped (owner decision H4). This is a review of the ledger text; the H9 sign-off of those rows, against the live pages, remains for Step 7. | `ai-workflow/claim-ledger.md` rows C8–C15 at `8a11207` |
| 2026-09-26 | H8 | PR #6 (Sprint 2 Step 6, the investigation pages) merged by the owner via `gh`. | PR #6: state `MERGED`, merged by `emkwambe` at 2026-09-26T17:42:37Z, merge commit `cb3d76d`, head `8ac2a19`. CI on `main` at `cb3d76d` (run 36259991876): `python-tests`, `web-build`, `docs-checks` all success |
| 2026-09-26 | H4 | Release PR #7 blocked by CI `docs-checks`: the README linked to the not-yet-deployed `/investigations` page (404). The owner chose option (b): keep the order (merge, then deploy); the README names the page in plain text in PR #7, and the link is restored in the post-deploy evidence PR. Options (a), deploying `main` before the merge, and (c), excluding the URL from the link check, were declined. | PR #7 CI run (lychee: 1 error, `[404] .../investigations`); correction log |
| 2026-09-26 | H8 | Release PR #7 (Sprint 2 Step 7) merged by the owner via `gh`. | PR #7: state `MERGED`, merged by `emkwambe` at 2026-09-26T17:56:06Z, merge commit `243c8c7`, head `e917e0b`. CI on `main` at `243c8c7` (run 36260773056): all three jobs success |
| 2026-09-26 | H8 (release) | On the owner's instruction after the merge: `main` at `243c8c7` (clean tree) deployed to production with `vercel deploy --prod` (deployment `dpl_DuBWWMFpVwAn2zTCnPNMRstamfsR`, READY, target production). Production smoke passed, then the annotated tag `v1.1.0` was created on `243c8c7` and pushed. | `ai-workflow/evidence/sprint-2/smoke_production.txt`; `git ls-remote --tags origin`: `refs/tags/v1.1.0` → tag object `d7c95bd`, peeled to `243c8c7` |
| 2026-09-26 | H8 | PR #8 (v1.1.0 evidence) merged by the owner via `gh`. | PR #8: state `MERGED`, merged by `emkwambe` at 2026-09-26T18:07:37Z, merge commit `d2f17de`, head `a5fc228`. CI on `main` at `d2f17de`: all three jobs success |
| 2026-09-26 | Owner review before H9 | (1) The later-purchases page's "two independent recomputations" was found not exactly accurate (only B1's figures were recomputed twice; only 4 of 30 Kaplan–Meier points and no intervals were independently recomputed). The owner approved the corrected wording on both pages. (2) The figure 28,152 appears in no committed file or commit on any branch (only in a session report); the owner decided to log it. | Correction log (two entries); `verify.json` check names; `git grep` and `git log --all -G` |
| 2026-09-26 | H8 | PR #9 (exact verification wording) merged by the owner in the browser. | PR #9: state `MERGED`, merged by `emkwambe` at 2026-09-26T18:21:16Z, merge commit `c153a16`, head `d700cd1`. CI on `main` at `c153a16` (run 36262241665): all three jobs success |
| 2026-09-26 | H8 (release v1.1.1) | On the owner's instruction: `main` at `c153a16` (clean) redeployed to production (deployment `dpl_D7RqiZWDFXjezThGpmpKA19AQWSq`, READY, target production). Production smoke passed 30/30. The corrected section-7 wording was confirmed live on the production domain on both investigation pages, with neither old phrase present. The annotated tag `v1.1.1` was then created on `c153a16` and pushed, so the live site corresponds to a tagged release. The CHANGELOG 1.1.1 entry follows in the next PR, because under the Governed tier every change to `main` goes through a PR; Claude Code flagged this ordering to the owner (it was not an owner decision). | `ai-workflow/evidence/sprint-2/smoke_production_v1.1.1.txt`; `git ls-remote --tags origin`: `refs/tags/v1.1.1` → tag object `d8af229`, peeled to `c153a16` |

The seed-stability check (H3-D5) is reported in the generated section below.

## Copilot code review

Not available to this account, as observed on PR #1 (details in `ai-workflow/tools.md`). PRs are reviewed by CI and the owner.

<!-- GENERATED BELOW by python -m funnel.verification_sprint2 from saved evidence, exports, and git history. Do not edit below this line by hand. -->

## Production

- Live site: https://ecommercefunnel-analytics.vercel.app
- Smoke test against production: `30/30 checks passed` (`ai-workflow/evidence/sprint-2/smoke_production.txt`).
- 390 px screenshots, light and dark: 18 page-theme combinations pass, 0 fail; WebP files in `ai-workflow/evidence/sprint-2/`.

## Full dbt builds (from clean trees)

| Commit | Clean | dbt | Tests run / expected | Models | Available before | Elapsed | Peak spill |
|---|---|---|---|---|---|---|---|
| `e335f67` | True | PASS=149 ERROR=0 | 134 / 134 | 15 | 3.75 GB | 1365.4 s | 10.55 GiB |
| `1512d76` | True | PASS=191 ERROR=0 | 170 / 170 | 21 | 5.06 GB | 1252.7 s | 10.50 GiB |

## Independent verification (`python -m funnel.verify`, latest run)

- Commit `7bc7bb5`, clean tree: True. 7.63 GB available before the run; 858.7 s; peak spill 21.44 GiB.
- All checks match: **True** (152 of 152): 83 for analysis A, 45 for analysis B, and the rest from Sprint 1. Counts and DECIMAL sums exactly, rates within 1e-09. Every check is in `ai-workflow/evidence/sprint-2/verify.json`.

## Analysis A: the two revenue figures (from investigation_revenue_gap.json)

- Revenue $229,932,953.94; revenue with repeat purchase events collapsed $211,426,365.64; difference $18,506,588.30, the value of 52,401 repeat purchase events in 41,340 (session, product) pairs.

| Dimension | Group | Share of the difference | Repeat purchase events |
|---|---|---|---|
| price_vs_first_purchase | Same price as the first purchase event | 99.27% | 52,071 |
| price_vs_first_purchase | Different price from the first purchase event | 0.73% | 330 |
| purchase_events_in_pair | 2 | 62.88% | 34,169 |
| purchase_events_in_pair | 3 | 19.85% | 10,278 |
| purchase_events_in_pair | 4 or more | 17.27% | 7,954 |

Threshold sensitivity (share of the difference within T): 0 s 0.00%; 1 s 0.09%; 5 s 0.18%; 10 s 0.36%; 30 s 1.68%; 60 s 24.45%; 5 min 88.85%; 30 min 98.49%; 1 h 99.20%.

## Analysis B: later purchases (from investigation_later_purchases.json and later_purchases.json)

| Spec | Population | Followed / eligible | Count share [95% CI] | Value share [95% CI] |
|---|---|---|---|---|
| B1 | sessions starting October 1–24, 2019 UTC | 36,786 / 263,018 | 13.99% [13.81%, 14.16%] | 13.40% [13.14%, 13.66%] |
| B2 | sessions starting October 1–28, 2019 UTC | 37,330 / 307,551 | 12.14% [11.98%, 12.29%] | 11.52% [11.29%, 11.73%] |
| B3 | sessions starting October 1–17, 2019 UTC | 27,057 / 166,694 | 16.23% [16.00%, 16.46%] | 15.65% [15.30%, 15.99%] |
| B5 | sessions starting October 1–24, 2019 UTC | 8,236 / 598,482 | 1.38% [1.34%, 1.41%] | 1.48% [1.42%, 1.53%] |
| B6 | sessions starting October 1–24, 2019 UTC | 27,611 / 231,758 | 11.91% [11.78%, 12.05%] | 11.24% [11.05%, 11.44%] |
| B7 | sessions starting October 1–24, 2019 UTC | 35,591 / 257,433 | 13.83% [13.65%, 14.00%] | 13.16% [12.89%, 13.41%] |
| B8 | sessions starting October 1–24, 2019 UTC | 36,780 / 262,781 | 14.00% [13.81%, 14.18%] | 13.41% [13.14%, 13.68%] |

Kaplan–Meier (all carted pairs with no purchase in the session, all of October): 1 d 10.01% [9.88%, 10.14%]; 3 d 12.21% [12.06%, 12.36%]; 7 d 13.81% [13.64%, 13.97%]; 14 d 15.10% [14.92%, 15.28%]; 30 d 16.29% [16.08%, 16.50%].

Cohort difference: sessions starting after October 24, 2019 UTC, KM 7-day 12.52% [12.18%, 12.88%], against 13.99% [13.81%, 14.16%] for sessions starting October 1–24, 2019 UTC.

Stop rules (pre-committed):

- identity: user_id checks 1-2 are zero and check 3 is 100%: **did not fire**
- R3 agreement: the B1 7-day count share lies inside the all-pairs KM 7-day 95% interval: **fired**. Resolution: Owner decision H4, 2026-09-26 (option A): B1 kept at 'shows', scoped to its population; the disagreement is disclosed and the late-October cohort difference reported as a finding. Records: ai-workflow/escalations/2026-09-26-B-R3-agreement.md, ai-workflow/sprint-2-verification.md.
- comparison baseline: the B1 count share is above the B5 count share: **did not fire**

Statistics run: commit `a013aff`, 7.69 GB available, 540.3 s.

### Seed-stability check (owner decision H3-D5)

| Seed | B1 count share 95% CI | B1 value share 95% CI | KM 7-day 95% CI |
|---|---|---|---|
| 20260926 | [13.809%, 14.163%] | [13.142%, 13.663%] | [13.641%, 13.968%] |
| 20260927 | [13.814%, 14.164%] | [13.148%, 13.660%] | [13.645%, 13.973%] |
| 20260928 | [13.809%, 14.160%] | [13.145%, 13.667%] | [13.645%, 13.971%] |
| 20260929 | [13.815%, 14.157%] | [13.144%, 13.667%] | [13.651%, 13.961%] |

The published intervals use the first seed. Across the four seeds, each bound moves by up to 0.0098%.

## Tests

`174 passed in 6.03s  (pytest_exit_code=0)`

## Correction log: 19 Sprint 2 entries

- Sprint 2 Step 0 · `.env.example` left out of the last direct commit to main (Claude Code; Claude Code's own review)
- Sprint 2 Step 3 · Export test pinned that no Changes entry touches decision D4 (Claude Code; Test or commit gate)
- Sprint 2 Step 4 · Wording guard could pass on nothing and did not check its injections (Claude Code; Human review)
- Sprint 2 Step 4 · Added wording-guard term `prove\w*` was over-broad (Project owner; Claude Code's own review)
- Sprint 2 Step 4 · Correction-log entry written outside the log's classification rules (Claude Code; Test or commit gate)
- Sprint 2 Step 4 · Commit message stated a test count before the gate reported it (Claude Code; Claude Code's own review)
- Sprint 2 Step 4 · Category export order was not fully determined (Claude Code; Test or commit gate)
- Sprint 2 Step 4 · Report described a smooth timing hump as bunching below 60 seconds (Claude Code; Claude Code's own review)
- Sprint 2 Step 4 · Exploratory gap histogram counted each pair's first event as a gap over 300 s (Claude Code; Claude Code's own review)
- Sprint 2 Step 5 · Export opened DuckDB without the shared memory settings (Claude Code; Claude Code's own review)
- Sprint 2 Step 5 · Independent Kaplan–Meier SQL failed when a time step removed everyone at risk (Claude Code; Test or commit gate)
- Sprint 2 Step 5 · Ledger row claimed an independent recomputation that did not exist (Claude Code; Claude Code's own review)
- Sprint 2 Step 6 · Legend-label test pinned the whole metrics index (Claude Code; Test or commit gate)
- Sprint 2 Step 6 · Long field paths in Sources lines widened the investigation pages at 390 px (Claude Code; Screenshot or smoke check)
- Sprint 2 Step 7 · Verification generator listed the timing groups that H4 kept unpublished (Claude Code; Claude Code's own review)
- Sprint 2 Step 7 · README linked to a production page before it was deployed (Claude Code; Claude Code's own review)
- Sprint 2 Step 7 · Screenshot script failed on nested routes when writing WebP evidence (Claude Code; Screenshot or smoke check)
- Sprint 2 Step 7 · Later-purchases page overstated its independent recomputation (Claude Code; Human review)
- Sprint 2 Step 4 · Report quoted a hand-added total (28,152) for duplicate cart rows (Claude Code; Human review)

## Sprint 2 commits on main (first parent)

- `03c1eed` Sprint 2 Step 0: adopt trio v2.3 / verified-analytics v2.1; last direct commit to main
- `6e0e959` Merge pull request #1 from emkwambe/sprint-2/governed-setup
- `76467d3` Merge pull request #2 from emkwambe/sprint-2/method-selection
- `ac825a5` Merge pull request #3 from emkwambe/sprint-2/metrics-changes
- `7249dd6` Merge pull request #4 from emkwambe/sprint-2/analysis-a
- `a091952` Merge pull request #5 from emkwambe/sprint-2/analysis-b
- `cb3d76d` Merge pull request #6 from emkwambe/sprint-2/site
- `243c8c7` Merge pull request #7 from emkwambe/sprint-2/release
- `d2f17de` Merge pull request #8 from emkwambe/sprint-2/v110-evidence
- `c153a16` Merge pull request #9 from emkwambe/sprint-2/verification-wording
