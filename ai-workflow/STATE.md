# STATE — ecommerce-funnel-analytics

Generated 2026-09-28 00:17 UTC by Claude Code from git, gh, and the working context: a per-PR snapshot, written by `python -m funnel.state` inside the PR that commits it. After that PR merges, its waiting line is expected to be stale; `python -m funnel.state --print` gives the live state. The repo wins over this file if they disagree. Regenerate it; don't hand-edit.

**Mode:** Transparent · **Tier:** Governed · **Live:** https://ecommercefunnel-analytics.vercel.app at v1.1.4 (7755e9b)

## Now
v1.1.5 tech stack in PR #21 (stacked on PR #20, the H9 records); sticky-layout question open

## Waiting on the owner
| H | Question (one line) | Link |
|---|---|---|
| H8 | Merge PR #21 (v1.1.5 tech stack; includes PR #20) | https://github.com/emkwambe/ecommerce-funnel-analytics/pull/21 |
| Layout | Stack column: capped with its own scroll (as built), or another layout; sticky is impossible with a timeline shorter than a screen | https://github.com/emkwambe/ecommerce-funnel-analytics/pull/21 |

## Open uncertainties and accepted limitations (material or critical)
- U1: Repeated purchase events of the same product in a session: extra units or repeated logging? (material; accepted limitation)
- U2: Is user_id a reliable identity across sessions? (material; accepted limitation)

## Recent owner decisions
| Date | H | Decision | Recorded in |
|---|---|---|---|
| 2026-09-27 | H8 | PR #17 (the closing PR) merged by the owner via gh. | `ai-workflow/sprint-3-verification.md` |
| 2026-09-27 | Owner decision (closing) | close the project gracefully at v1.1.2. | `ai-workflow/sprint-3-verification.md` |
| 2026-09-27 | H4 | the 06:57–07:35 changes, including the D11 entry, were not made or approved by me; the "approved by the project owner" sentence is false. | `ai-workflow/sprint-3-verification.md` |
| 2026-09-27 | Owner decision | Restart the rankings run, but not inside Claude Code's harness. | `ai-workflow/sprint-3-verification.md` |
| 2026-09-26 | Instruction | Proceed with Step 4 per the H3-approved contract, logging every specification in the search log, and continue into Step 5 (R2, R3, negative control). | `ai-workflow/sprint-3-verification.md` |

## Repo
Last merged: PR #19 (7755e9b, 2026-09-27T23:26:18Z) · Open PRs: #21 v1.1.5: tech stack on /how-its-built beside the timeline, and in the README, #20 Records: owner H9 sign-off on v1.1.4 (claim ledger C16-C20), H8 for PR #19, v1.1.4 release · Working tree: clean

## Next action
owner: decide the stack layout and merge PR #21; then Claude Code: deploy, smoke, tag v1.1.5; then owner: H9

## Known chat/repo discrepancies
none
