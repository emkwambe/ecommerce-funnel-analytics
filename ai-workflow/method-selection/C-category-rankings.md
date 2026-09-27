# Method Selection — C. Which categories convert viewing sessions most often, allowing for size?

Template: verified-analytics-project v2.2.0 (`assets/templates/method-selection.md`). Written in Sprint 3 Steps 1 and 2 (2026-09-26), before any Sprint 3 quantity is computed. **Status: approved by the owner at H3 on 2026-09-26, with all recommendations C-D1 to C-D10 as written.** It was approved together with the `docs/metrics.md` Changes entry "Sprint 3: category session conversion and its size-adjusted ranking". See "Owner decisions" at the end. Epistemic risk: **material** (the plan's risk classification). Any slow-down trigger in `ai-workflow/sprint-3.md` raises it to consequential.

**What was looked at before writing this record.** Only exposure counts and structure: the number of top-level categories and full codes, and each one's `funnel_pairs` (category-sessions), read from the committed `web/public/data/funnel_category.json`. The output was printed with only the `category` and `funnel_pairs` fields. No purchase count, rate, or revenue was read. **Disclosure:** the same file has published `funnel_pairs_with_purchase` since Sprint 1, so candidate A (the raw rate) is computable from public data and was visible to anyone who read the category funnel page. This lock is therefore not blind to the raw outcome. It does fix the method, the threshold, and the claim rules before any shrinkage, bootstrap, or ranking output exists.

**Question:** "Among viewing sessions, which top-level categories most often include a purchase in the category, and which differences are larger than size and chance can explain?"

**Question type:** ranking (descriptive). **Not causal.**

**Decision supported:** where the Sprint 3 test-recommendation framing (`ai-workflow/framing-test-recommendation.md`, Step 8) looks first. A category that is separably low is a candidate area for a test. A category that isn't separable from its neighbors isn't singled out. The ranking supports no uplift estimate.

**Estimand:** for each top-level category c, P(the category-session includes a purchase of a product in c), where a category-session is a (valid session, c) pair entered by a view in c (metrics.md §9 funnel population), over the file's full date range (October 2019, UTC). The size-adjusted estimate is its empirical-Bayes posterior mean. The ordering and the 90% rank intervals are the published targets.

**Claim ceiling** (the plan, verbatim): "Categories are ordered by estimated session conversion. Two categories are described as different only where their rank intervals don't overlap. This describes the period in the file and doesn't explain why categories differ."

## Data-generating process (relevant features)

- **Few, large groups at the top level.** There are 13 known top-level categories plus "unknown". The smallest known one has 2,853 category-sessions, and the largest has millions (`funnel_category.json`). At these sizes shrinkage toward the pooled rate is expected to be negligible, and the prior is fitted from only 13 points. The full-code level (126 known codes; smallest 144 category-sessions; 9 below 1,000; median 15,507) is where size adjustment matters (decision C-D1).
- **Clustering by user and by session.** One user contributes many sessions, and one session contributes a category-session to every category it viewed. Category-sessions are not independent within a category, or across categories. The beta-binomial model's n is therefore a nominal size, and the effective size is smaller. The user-clustered bootstrap carries this into the intervals, but not into the amount of shrinkage (failure condition F3).
- **Missing category.** 13,515,609 raw events (share 0.318398) have no `category_code` (`docs/data-profile.md` §6). "unknown" is the second-largest group of category-sessions and is excluded from the ranking. If missing codes fall unevenly across what would have been categories, the ranking describes coded products only. There's a sensitivity for sessions with no missing-code event.
- **Heterogeneous categories.** A top-level category mixes subcategories with different rates (for example, a large subcategory inside "electronics"). Its rate reflects that mix, not a property of the category as a whole. The page says so.
- **Purchases without a view in the category.** Purchases in sessions that never viewed the category aren't in the population by definition (§9). Purchases whose product differs from the viewed products do count.
- **Session boundaries as logged.** Technical session splits (a visit broken into several `user_session` values) can separate a view from the purchase. Where this varies by category, the rates differ for reasons unrelated to shopping behavior. This is covered by the adversarial checklist (Step 6), using the Sprint 2 overlapping-session diagnostic.
- **Heavy or automated users.** A few users with extreme activity can dominate a small category. This is covered by the 99.9th-percentile sensitivity.
- **Calendar.** One month. The ranking describes October 2019 only.

## Candidate methods

| Method | Assumptions | Verifiable how? | Fits this data-generating process? | Verdict |
|---|---|---|---|---|
| A. Raw rate x/n with a minimum-n cutoff | Sampling error is negligible above the cutoff | The bootstrap interval width near the cutoff | At the top level, yes (large n). At the code level it ranks noise near the cutoff | **rejected as primary**: shown beside the estimate as the raw rate |
| B. Empirical-Bayes beta-binomial: prior fitted by maximum likelihood of the beta-binomial marginal; rank by posterior mean; rank intervals from the user-clustered bootstrap with the prior refitted in each resample | Category rates are exchangeable draws from one unimodal Beta; within a category, category-sessions are binomial given the rate | Prior fit diagnostics (F1, F2); the method-of-moments cross-check; the design effect (F3) | Yes at both levels, with F3 as the main caveat | **chosen (primary)**, as the H1 decision requires |
| C. Wilson lower bound (95%) per category | Binomial sampling, independent category-sessions | The comparison with B | Conservative and prior-free; ignores clustering | **chosen as R3**: rank correlation with B, and every category whose separable status differs between the two |
| D. Hierarchical model (full Bayes, MCMC) with a user random effect | A correct random-effects model | Posterior predictive checks | Would handle clustering in the shrinkage | **rejected**: a large build for 13 categories, and it adds a dependency. Reconsider if F3 fires at the code level |
| E. Session-level bootstrap | Sessions are independent | — | No: one user's sessions aren't independent (Sprint 2 analysis B) | **rejected** |
| F. Separability by a per-pair bootstrap probability, P(θi > θj) ≥ 0.95 (an alternative to non-overlapping rank intervals) | The bootstrap distribution of each pairwise difference is calibrated | Coverage under the negative control | Better calibrated for a single pair, but it needs a multiplicity rule across pairs | **rejected** (owner decision at H3, 2026-09-26): the rank-interval rule stays as the claim rule, and this rule is **not computed** |

**Uncertainty:** a cluster bootstrap at the `user_id` level (resample users with replacement, keeping all their category-sessions), 2,000 resamples, seed 20260926, with seed stability checked on 20260927 to 20260929. The prior is refitted and the categories re-ranked in every resample, so the rank interval includes prior uncertainty. The implementation follows Sprint 2's user-sum approach: one row per (user, category) with the counts needed, and resample weights drawn per user.

**Negative control (Step 5):** permute category labels across category-sessions, keeping each category's number of category-sessions, then rerun B with the bootstrap. The expected result is no separable pairs. Proposed specification (C-D6): 5 permutations with seeds 20261001 to 20261005, each with the full bootstrap. **Stop rule:** any separable pair in any permutation stops the work, because it would mean the uncertainty method is broken.

## Failure conditions

- **F1. A single prior is inappropriate.** For example, the category rates are bimodal, or one category is far from the rest. Diagnostic: a plot of raw rates with the fitted Beta density, the maximum-likelihood versus method-of-moments fits, and a leave-one-out prior refit. If one category moves the prior mean by more than the width of its own interval, report it and stop for H4.
- **F2. Prior collapse.** The fitted α + β is extremely large (everything is shrunk to the pooled rate) or near zero (no shrinkage). This is a slow-down trigger. Report α + β against the category sizes.
- **F3. Clustering understates the shrinkage.** Design effect = (bootstrap variance of a category's raw rate) ÷ (binomial variance p(1 − p)/n). If the median design effect over ranked categories is above 2, shrinkage by nominal n is too weak. Report it and stop for H4, with an effective-n adjustment as the proposed fix (not pre-approved).
- **F4. R2 mismatch** (any count, or any posterior mean beyond 1e-9 relative): stop; it indicates a bug in one path.
- **F5. B and C disagree** on separability for more than 2 categories (the plan's "more than a few", made numeric): slow-down trigger.
- **F6. The negative control shows separation:** stop (above).
- **F7. The top-ranked category has fewer category-sessions than the median** of ranked categories: slow-down trigger (plan).
- **F8. Sensitivity movement:** any category's rank changes by more than 2 places, or any pair's separable status changes, under the minimum-size or missing-code sensitivities: slow-down trigger (plan).
- **F9. Reconciliation failure** with `mart_funnel_category` (metrics.md entry, item 5): stop.

## Robustness plan (all pre-specified; every run logged in `ai-workflow/search-log.md`)

| # | Specification | Role |
|---|---|---|
| C1 | Top level; B with a maximum-likelihood prior; minimum size 1,000; 2,000 user-clustered resamples, seed 20260926; 90% rank intervals | primary |
| C2 | C1 with seeds 20260927 to 20260929 | seed stability |
| C3 | Wilson lower bound ranking; rank correlation with C1; separable-status differences | R3 |
| C4 | Method-of-moments prior | sensitivity (prior fit) |
| C5 | Minimum size 500 and 2,000 | sensitivity (threshold; at the top level it changes nothing unless C-D1 adds codes) |
| C6 | Excluding sessions longer than 24 hours | sensitivity (§3 practice) |
| C7 | Excluding users above the 99.9th percentile of events | sensitivity (bot-like users, Sprint 2 B7 rule) |
| C8 | Sessions with no event of a product with a missing code | sensitivity (missing-category handling) |
| C9 | Label permutation × 5 | negative control |
| C10 | Design effect per category; leave-one-out prior | diagnostics F1, F3 |
| C11 | Revenue per category-session, both U1 figures, 90% intervals | secondary metric |
| R2 | An independent recomputation of the C1 counts and posterior means (decision C-D7) | reproduction |

## Decisions needed (H3)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| C-D1 | Ranking level | (a) top level only (plan and §9 headline); (b) top level as the headline plus a full-code drill-down with the same rules; (c) full code only | **(b)**: the top level answers the plan as written, but with 13 large categories shrinkage barely acts. The code level is where "honest about sample size" has content. It adds one more ranked table and its own negative control |
| C-D2 | Minimum reporting size, and whether categories below it help fit the prior | 1,000 category-sessions; categories below it are excluded from ranking and from the prior fit, or excluded from ranking but kept in the prior fit | **1,000, excluded from both**: simplest, and it keeps the prior from being set by the noisiest groups |
| C-D3 | Prior fitting | Maximum likelihood (beta-binomial marginal), with method of moments as a sensitivity; or the reverse | **Maximum likelihood primary** |
| C-D4 | Bootstrap | User-clustered, 2,000 resamples, seed 20260926, 90% percentile intervals, prior refitted per resample | **Approve** |
| C-D5 | Separability rule | (a) non-overlapping 90% rank intervals (plan); (b) a pairwise bootstrap probability P(θi > θj) ≥ 0.95 | **(a) as the claim rule** (the owner's claim ceiling). It is conservative. See the Step 1 report, objection 3 |
| C-D6 | Negative control | 5 label permutations, seeds 20261001 to 20261005, full bootstrap each; any separable pair stops the work | **Approve** (the plan says "essentially no" separable pairs. This makes it a numeric rule of zero) |
| C-D7 | R2 path | (a) `funnel.verify`-style independent DuckDB SQL from the Parquet file (not the dbt models) for the counts, plus an independent posterior computation; (b) a different engine (pyarrow compute) for the counts | **(a)**: only DuckDB, pandas, and pyarrow are installed; pandas can't hold the events, and a pyarrow group-by over the event file risks the 3 GB memory floor. The plan asks for a different engine, so (a) is a deviation from the plan that needs the owner's approval |
| C-D8 | Secondary revenue metric | As defined in item 11 of the draft entry (category-sessions population, both U1 figures, not ranked, 90% intervals) | **Approve** |
| C-D9 | Sensitivities C4 to C8 | Include all, or drop any | **Include all** |
| C-D10 | Claim ceiling | The plan's wording, verbatim | **Approve** |

## Owner decisions (H3, 2026-09-26, owner-decided)

The owner approved the `docs/metrics.md` Changes entry and this record with **all recommendations C-D1 to C-D10 as written**, including:

- **C-D1:** the top-level headline, with a full-code drill-down where shrinkage applies.
- **C-D2:** a minimum of 1,000 category-sessions. Codes below it are excluded from the ranking and from the prior fit, and shown as "insufficient data".
- **C-D6:** zero separable pairs across 5 shuffles.
- **C-D7:** R2 by independent DuckDB SQL (not dbt) plus an independently written posterior. The page describes it exactly as "an independent implementation, using the same engine".
- **C-D8:** revenue per category-session as drafted, both U1 figures, never ranked.

On the Step 1 objections:

- **Objection 2** (the approval is outcome-aware) is recorded as a disclosure in this record: see "What was looked at before writing this record" at the top.
- **Objection 3:** the rank-interval separability rule stays. The per-pair probability rule is recorded as a rejected alternative (candidate F) and is not computed.
