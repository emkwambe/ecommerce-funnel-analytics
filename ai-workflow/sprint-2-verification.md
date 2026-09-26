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

## Seed-stability check (H3-D5)

To be filled in Step 5: the primary interval bounds (items 9, 10, and 12 at 7 days) for seed 20260926 and for seeds 20260927, 20260928, and 20260929.

## Copilot code review

Not available to this account, as observed on PR #1 (details in `ai-workflow/tools.md`). PRs are reviewed by CI and the owner.
