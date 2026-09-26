# Sprint 2 verification

Started in Sprint 2 Step 1 to record owner decisions as they are made. Evidence sections (dbt, verify, smoke, analyses A and B) are added in Step 7.

## Owner decisions

Every decision below was made by the project owner (Eddy Mkwambe). Claude Code carried out the actions and recorded the evidence.

| Date | Checkpoint | Decision (owner-decided) | Artifact / evidence |
|---|---|---|---|
| 2026-09-26 | H1 | Sprint 2 framing approved as written in `ai-workflow/sprint-2.md`, including the Sprint 2/3/4 split (recommendations, size-adjusted rankings, Tableau, and the agent deferred to Sprints 3–4). | `ai-workflow/sprint-2.md` (committed in `03c1eed`) |
| 2026-09-26 | H6 | Branch protection on `main` approved as proposed, applied by Claude Code on the owner's instruction: PR required (0 approvals: the owner cannot approve their own PR); required status checks `python-tests`, `web-build`, `docs-checks`; branches up to date before merging; enforced for admins; no force pushes; no deletion. | GitHub branch protection API, read back after applying: `{"checks":["python-tests","web-build","docs-checks"],"deletions":false,"enforce_admins":true,"force_push":false,"pr_required":true,"strict":true}` |
| 2026-09-26 | — (release record) | The `CHANGELOG.md` v1.0.0 entry for the Sprint 1 release at `a96f7e0` is accepted. An annotated retroactive tag `v1.0.0` is created at `a96f7e0` with the message "Retroactive tag for the Sprint 1 release (a96f7e0), created 2026-09-26 during Sprint 2; v1.0.1 followed at b7f0044", and pushed. | `git ls-remote --tags origin`: `refs/tags/v1.0.0` → tag object `47bc571`, peeled to `a96f7e0`. The CHANGELOG v1.0.0 entry and `ai-workflow/tools.md` were updated to name the tag |

## Copilot code review

Not available to this account, as observed on PR #1 (details in `ai-workflow/tools.md`). PRs are reviewed by CI and the owner.
