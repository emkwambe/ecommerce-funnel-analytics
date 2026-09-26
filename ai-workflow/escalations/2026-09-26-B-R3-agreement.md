# Escalation Brief — Analysis B: the R3 agreement rule fired

**Class:** material. **Raised by:** Claude Code, under the pre-committed stop rule of owner decision B-D6 (method record B; `docs/metrics.md` Changes 2026-09-26, B item 12). **Blocks:** B's export, claim-ledger rows, and pages; any interpretive sentence about B.

All values are in `ai-workflow/evidence/sprint-2/later_purchases.json` (run 3, clean tree at `a013aff`). Field names are cited here instead of typed figures (CLAUDE.md rule 1).

1. **The ambiguity:** the fixed-window B1 7-day count share (`estimates.B1.count_share`) lies outside the all-pairs Kaplan–Meier 7-day 95% interval (`stop_rules[1].km_7_day_interval`), just above its upper bound. The rule says stop and escalate with the cohort diagnostic, treating neither method as wrong. The question is what B may publish, and at what tier.

2. **Alternatives:**
   - A: Keep B1 (pre-specified primary) at "shows". Publish the R3 outcome as run: the methods disagreed narrowly, and the cohort diagnostic attributes the gap to a difference between cart-session cohorts, not to either method. Publish the KM curve with that caveat, and never state R3 agreement. → B1 and its intervals are published unchanged, and the disagreement is disclosed beside them.
   - B: Downgrade every B claim to "suggests" (a single path validated only by R2, with R3 unresolved). → Same numbers, weaker wording throughout the B page and ledger.
   - C: Add a cohort-matched KM (pairs from sessions starting by the 7-day cutoff) as the R3 comparison, through a new Changes entry (H3). → Agreement follows by construction (see evidence 3), so it adds no independent check; not recommended as a substitute for R3.
   - D: Withhold B until more follow-up data is available (a later month of the same source). → Out of this sprint's scope; needs a new ingest (provenance event) and H1.

3. **Evidence gathered:**
   - **Implementations agree on the same population.** The KM 7-day estimate for the cohort of pairs from sessions starting by the 7-day cutoff (`cohort_diagnostic.by_7_day_cutoff.count`) equals `estimates.B1.count_share` to about 1e-13. In that cohort, no pair is censored before 7 days, so KM and the fixed window must coincide, and they do. The dbt test `assert_later_purchase_reconciles` also matches that cohort to B1 pair for pair. R2 (`funnel.verify`, `B1:*`) matches exactly.
   - **The populations differ.** The later cohort (`cohort_diagnostic.after_7_day_cutoff`) has a lower KM 7-day estimate. Its interval does not overlap the earlier cohort's. The all-pairs KM pools both cohorts, so its 7-day value sits below the fixed-window estimate, which uses only the earlier cohort.
   - **This bears on KM's assumption.** KM treats censoring as non-informative, which needs the follow-up hazard to be the same regardless of when the cart session started. The cohort difference shows it is not the same across October. The method record listed calendar effects as the first candidate cause.
   - **Size:** the fixed-window share exceeds the KM upper bound by less than the width of the rounding shown on a page (`stop_rules[1]`). The rule is binary, and its size does not change what fired.
   - **Stable and not driven by a few users:** the rule fires under all four seeds. The KM 7-day upper bound stays below the B1 share for every seed in `seed_stability`, though its movement across seeds is of the same order as the gap. Dominance is below its limit (`dominance`).
   - **Not a data problem:** the identity checks pass (`checks.user_id_check:*`), and the comparison-baseline rule did not fire (`stop_rules[2]`).

4. **Consequences of each:**
   - A publishes the pre-specified estimate with full disclosure. Risk: a reader may take the KM curve as describing all of October; mitigated by the caveat and the cohort figures.
   - B is the most conservative option, and it weakens even the R2-verified, pre-specified B1.
   - C adds a change to a locked contract for no evidential gain.
   - D delays B indefinitely.
   - All options are reversible until publication.

5. **Recommendation:** A. The rule did its job: it exposed a real cohort difference. Both implementations are internally consistent, and the pre-specified B1 is unaffected. Disclose it rather than downgrade the verified estimate or re-specify R3. Claim-tier wording for B stays within the H3-D4 ceiling ("shows"), and the page states that R3 did not agree and why.

6. **Decision needed from the owner (H4):** A, B, C, or D?
