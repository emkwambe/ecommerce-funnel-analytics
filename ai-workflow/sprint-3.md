# Sprint 3: Size-adjusted category rankings (+ framing for the test recommendation, product recommendations, and the agent)

**Project:** ecommerce-funnel-analytics · **Mode:** Transparent · **Tier:** Governed
**Planned:** 2026-09-26 by the command center (Project chat) with the owner; reviewed and merged with the long-running command-center chat (see "Review changes" at the end)
**Base:** `sprint-3/carryover` at 720bb50 (two commits ahead of main)
**Target release:** v1.2.0

## Owner decisions taken at planning (record all three in `ai-workflow/sprint-3-verification.md`, owner-decisions table, dated 2026-09-26)

Record these as owner-decided **only** as the owner stated them. Each row cites where it was decided (the Project chat planning session). If any wording here differs from what the owner said, ask before recording.

| H | Decision |
|---|---|
| H1 | Sprint 3 scope: carryover PR, then size-adjusted category rankings end to end. **The test recommendation (the business question's "what should the team test first?")**, product recommendations, and the agent get framing documents only, with no code. Tableau is deferred until a publishing check (Step 3) confirms that aggregates can be published without exposing row-level data. |
| H1 | Primary ranking metric: **session conversion**, meaning the share of category-sessions that include a purchase in that category, shrunk toward the pooled rate for small categories. Revenue per category-session is secondary and always shows both U1 figures. |
| H5 | U1 and U2 are reclassified from *open* to **accepted limitation**, with binding constraints: (a) every revenue-based figure shows both the primary and the repeat-collapsed value (U1); (b) every metric that links events across sessions carries the U2 caveat on the page and in its claim row. Both stay in the register and on the pages. |

## Goal

Publish a category ranking by session conversion that is honest about sample size. Small categories are shrunk rather than crowned, rank uncertainty is shown, and the page says only what the rank intervals support.

## Risk classification

- **Execution complexity:** moderate.
- **Risk:** material (portfolio publication; descriptive ranking with interpretation). Epistemic risk is the driver: rankings of rates are a classic place to fool ourselves, because small groups sit at both extremes by chance.
- **Escalation rule:** any slow-down trigger (below) raises this to consequential, which requires R3, a full adversarial review, and H9 sign-off before publishing.

## Preflight (stop if any fails)

1. `python -m funnel.state --print` matches the handshake above: PR #13 merged, no open PRs, clean tree, on `sprint-3/carryover` at 720bb50.
2. Test gate green locally: 186 passed.
3. `docs/metrics.md` has no unapproved Changes entries pending.
4. Nothing under `data\` is committed (leak check passes).

## Steps

### Step 0: Carryover PR (H8)
Open a PR from `sprint-3/carryover` to main. Inside this PR:
- regenerate the committed `ai-workflow/STATE.md` as this PR's snapshot;
- add the three planning decisions above to `sprint-3-verification.md`, and update U1 and U2 in `uncertainty-register.md` to *accepted limitation (H5, 2026-09-26)* with the constraints quoted verbatim;
- add a dated note to the Sprint 2 report giving the current Sprint 2 correction-log count, **computed by code** from the log (never hand-added). Annotate the report; don't rewrite it;
- update CHANGELOG Unreleased.

CI must pass *on the PR* (the first CI run for these commits). Copilot review isn't available on this account (see `tools.md`), so review is CI plus the owner. **Stop:** report the PR link and the CI run ID, then wait for my H8 merge. No rankings work starts until Step 0 is merged.

### Step 1: Question gate and contract draft (H1 recorded, H3 pending)
Draft a dated **Changes** entry in `docs/metrics.md` defining:
- **Question type:** ranking (descriptive). No causal language.
- **Estimand:** for each category, P(purchase in category | session viewed at least one product in the category), over the file's full date range.
- **Unit:** category-session. **Reuse the Sprint 1 category-funnel grain and population** (metrics.md §9: (session, top-level category) pairs entered by a view), so that this ranking and the existing category funnel reconcile; state the reconciliation as a test. Define precisely how a session touching several categories counts, and how events with a missing `category_code` are handled (excluded and counted, with the exclusion count published). Take the missing rate from the data profile and don't re-derive it.
- **Exclusions:** reuse the Sprint 0/2 session rules (multi-user sessions excluded, per metrics.md §3).
- **Minimum reporting size:** state the threshold and its rationale. Categories below it are shown as "insufficient data", not ranked.
- **Claim ceiling:** "Categories are ordered by estimated session conversion. Two categories are described as different only where their rank intervals don't overlap. This describes the period in the file and doesn't explain why categories differ."

**Stop:** present the draft entry together with the Step 2 record for a single H3 approval. Compute nothing on outcomes before approval.

### Step 2: Method-selection record (`assets/templates/method-selection.md`)
Walk the chain: question → estimand → data-generating process → assumptions → candidates → rationale → failure conditions. The candidates to compare:
- **A. Raw rate with a minimum-n cutoff.** Simple, but it ranks noise near the cutoff.
- **B. Empirical-Bayes beta-binomial shrinkage** (proposed primary). Fit the prior from all categories by method of moments or maximum likelihood, and rank by posterior mean.
- **C. Wilson lower bound.** Conservative and prior-free. It serves as the R3 path.

Rank uncertainty comes from a **user-clustered** bootstrap (resample users with all their sessions, as in Sprint 2 analysis B; not sessions or events, because one user's sessions aren't independent), reporting a 90% rank interval for each category. State a fixed seed and the number of resamples. Include the conditions under which B fails: for example, a bimodal category distribution that makes a single prior inappropriate. This record goes to H3 together with Step 1.

### Step 3: Publishing check for Tableau (evidence only)
The dataset license question was settled in Sprint 0 (aggregates and findings only, with attribution; cite `docs/data-source.md`). The open question is Tableau Public's own behavior: **can a workbook built only from the committed aggregate exports be published without exposing row-level data** (Tableau Public lets viewers download workbook data)? Answer from Tableau's current official documentation, quoting it verbatim with URLs, and confirm that the only data source would be the aggregate exports. Record the answer in `sprint-3-verification.md`. Build nothing in Tableau. If the answer is unclear, file it as a new uncertainty item for a later H2.

### Step 4: Execute (after the H3 approval)
Implement per the approved contract. Log **every** specification tried in `ai-workflow/search-log.md` (prior-fitting method, thresholds, seeds), labeled pre-specified or exploratory. Changing the threshold after seeing results is a deviation that needs a new H3 entry.

### Step 5: Reproduction and falsification
- **R2:** an independent implementation of the headline table, using a different engine from the primary path (for example, DuckDB SQL if the primary path is pandas). It must match within a stated tolerance.
- **R3:** the Wilson-lower-bound ranking. Report the rank correlation with B, and list every category whose separable/not-separable status differs between the two methods.
- **Negative control:** permute category labels across category-sessions and rerun B with the bootstrap. Expected result: essentially no separable pairs. If the permuted data still shows separation, stop, because the uncertainty method is broken.

### Step 6: False-discovery gate and adversarial review (checklist pass)
Answer the six gate questions (number of specifications examined, post-hoc selection, reuse, adjustment, robustness, mechanism). Adversarial checklist: Is the top category large, or is it a shrinkage artifact? Do any results depend on the missing-category handling? Does session-splitting or bot-like sessions inflate any single category? Check each against the data and cite the evidence.

### Step 7: Claim ledger and page (H9)
Add claim rows for each published statement, with wording matched to its strength (for example, "suggests"). Build the rankings page with a dot-and-interval chart sorted by posterior mean, with small categories shown separately and a Sources line. Show the secondary revenue metric with both U1 figures. Update the /data and how-it's-built pages.
Owner review may happen on a preview deploy, but **the H9 sign-off happens after the production deploy (Step 9), on the live URL**. Claims are signed off as published.

### Step 8: Framing documents (no code)
Write three documents:
- `ai-workflow/framing-test-recommendation.md`: **the business question's third part, "what should the team test first?"** It uses the Sprint 1–3 findings (purchase paths, later purchases, the size-adjusted ranking) to propose candidate experiments. **Claim ceiling:** observational data can only *prioritize candidate tests*; it can never promise uplift. Any expected-effect figure is a labeled scenario estimate and requires a metrics.md Changes entry (§8) before it appears anywhere;
- `ai-workflow/framing-recommendations.md`: product recommendations (a recommender), which is a different question from the test recommendation;
- `ai-workflow/framing-agent.md`.

Each covers:
- the decision it supports;
- the candidate question types and estimands;
- its exposure to U1 and U2. Recommendations are heavily exposed: co-purchase counts are inflated by U1, and "bought later" depends on U2;
- the candidate methods, with a popularity baseline required for recommendations;
- a holdout design (temporal split);
- the claim ceiling;
- for the agent: what it may answer (only claim-ledger rows and contract metrics), how it refuses beyond that, and any credential needs (H7);
- the open H1 questions for me, each as one line.

These documents are inputs to Sprint 4 planning, not decisions.

### Step 9: Release (H8), deploy, smoke
Open the release PR with STATE.md regenerated inside it. After CI passes, **stop for H8**. After the merge: deploy to production, run the smoke suite against the live URL including the new rankings page, and paste the output verbatim. Tag v1.2.0. **Then stop for H9** on the live rankings page (Step 7's claim rows), and record the sign-off in a records PR, never a snapshot-only PR.

## Slow-down triggers specific to this sprint
- The top-ranked category has fewer category-sessions than the median.
- B and C disagree on separability for more than a few categories.
- The negative control shows any separable pairs.
- Results move noticeably when the minimum-n threshold or missing-category handling changes slightly.
- The shrinkage prior is extremely tight (everything collapses to the pooled rate) or extremely loose (no shrinkage at all).

## Definition of Done
- [ ] Step 0 merged by the owner (H8); STATE.md snapshot regenerated in that PR
- [ ] H1 and H5 decisions recorded, U1 and U2 updated to accepted limitation with constraints
- [ ] metrics.md Changes entry and method-selection record approved (H3) **before** any outcome computation
- [ ] Search log complete, including failed and exploratory specifications
- [ ] R2 match within tolerance; R3 comparison and negative control reported verbatim
- [ ] False-discovery answers and adversarial checklist committed
- [ ] Claim rows signed off (H9) **on the live production page**; page wording matches ledger tier; U1/U2 constraints visibly honored
- [ ] Tableau publishing answer recorded with quoted official documentation
- [ ] All three framing documents committed, including the test recommendation
- [ ] Release merged (H8), production deploy done, smoke green against the live URL, v1.2.0 tagged
- [ ] Failure-patterns check done; correction log updated; no open critical uncertainty
- [ ] **Correctness level stated:** target is *methodologically sound* for the ranking. *Empirically valid* may be claimed only if R2, R3, and the negative control all pass. No causal claim is made.

## Final report format
Verbatim command outputs (tests, CI run IDs, R2/R3/negative-control tables, smoke), the correctness level reached, what's established, what's assumed, what's uncertain, and any pending H-checkpoint as a one-line question.

## Review changes (merged 2026-09-26)

The long-running command-center chat reviewed the Project chat's plan. Changes made:
1. **Restored the business question's third part.** "What should the team test first?" had been conflated with product recommendations. It now has its own framing document and claim ceiling.
2. **The bootstrap is user-clustered**, not session-level, following Sprint 2.
3. **H9 happens on the live production page**, not a preview.
4. **The correction-log count is computed by code**, not hand-added.
5. **Copilot review removed** (unavailable on this account).
6. **The Tableau check targets Tableau Public's data-exposure behavior**; the dataset license was settled in Sprint 0.
7. **The ranking reuses the Sprint 1 category-funnel grain**, with a reconciliation test.
8. **Owner decisions** are recorded only as stated, and cite where they were made.
