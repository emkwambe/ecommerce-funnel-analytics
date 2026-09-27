# Escalation brief: Sprint 3 category ranking, run identity and fired stop rules (H4)

**Date:** 2026-09-27 · **Written by:** Claude Code (executor) · **For:** the project owner, to decide with the command center
**Status:** decided at H4 on 2026-09-27 (§5): P1 with quarantine, then option A. Nothing has been published. R2 has not been run. Run 4's `rankings.json` was never opened by Claude Code; it is preserved on the quarantine branch. No specification was changed by Claude Code.

## 1. Which run produced the log and `rankings.json`

**The log the owner read is run 4, not run 3.** Run 4 ran on an uncommitted, unrecorded change to the pipeline. What is known, all from file metadata, git, and the logs (times are local, UTC−4):

| Time (2026-09-27) | Event | Evidence |
|---|---|---|
| 01:53:26 | **Run 3** starts in the owner's window, PID 6528, code `015a80f`. Memory gate 6.59 GB; resume key: code `966532351633`, marts `8605ac0bfff3` | log lines read by Claude Code at 01:5x; process start time from Windows |
| 03:28 | Run 3 still running, at top-level C9 shuffle 4 of 5; no exit-code file | Claude Code's one-off read-only check |
| 03:28 → 06:57 | Unknown. Run 3 was estimated to end at about 05:30–06:00. Whether and how it ended is **not recoverable**: `data\rankings_run3.log`, `rankings_exit_code.txt`, and `rankings_shell_exit_code.txt` no longer exist | directory listing at 12:07 |
| 06:57:44, 07:02:22 | `analysis/auto_audit.py` and `analysis/auto_bot_exclusion.py` created (untracked). Both load the full Parquet file into pandas and compute auto-category conversion rates, with and without user 512475445 | file contents and times |
| 07:07:49 | `pipeline/models/staging/stg_events.sql` edited: `where user_id != 512475445` before deduplication (uncommitted) | `git diff` |
| 07:12:31 | `docs/metrics.md` (and its web copy) gets a new Changes entry, "2026-09-27 · Bot exclusion at source (Section 2, D11)" (uncommitted) | `git diff` |
| 07:13:28–07:30:53 | `dbt run` of 21 models directly, **not** through `funnel.build`: no memory or dataset-hash gate, and no build record (`evidence/sprint-3/dbt_build_runs.json` is unchanged since 2026-09-26 22:05) | `data\dbt_rebuild_run3_botfix.log` (dbt prints UTC: 11:13–11:30) |
| 07:31:37–07:32:40 | `dbt test`: 192 pass, **1 fail: `assert_dedup_reconciles`** | `data\dbt_test_run3_botfix.log` |
| 07:34:07 | `pipeline/models/staging/stg_dedup_audit.sql` edited to apply the same filter (uncommitted) | `git diff` |
| 07:35:31 | Last write to `data\warehouse.duckdb`. No log exists for this write, and whether `assert_dedup_reconciles` passes now is unknown | file time |
| 08:06:54–11:40:56 | **Run 4**: memory gate 8.61 GB; resume key: code `966532351633` (the committed `015a80f` code), data `fedd938409b5`, marts **`540b7049d6ac`** (the rebuilt marts). The log is UTF-16, so it was redirected by Windows PowerShell 5 or cmd, not by the PowerShell 7 command given for run 3. The log ends with "rules fired: …", and **no exit code was recorded**: neither exit-code file exists | `data\rankings_run4.log` |
| 11:40 | `ai-workflow/evidence/sprint-3/rankings.json` written (untracked); every partial file under `data\rankings_partial\` rewritten between 08:13 and 11:40 | file times |

**Consequences:**
- **Run 3's output is gone.** Its partial files carried the old mart key, so run 4 recomputed and overwrote every part. If run 3 wrote a `rankings.json`, run 4 overwrote it.
- **Run 4's results come from a pipeline that isn't the H3-approved contract.** The staging change and the D11 entry are uncommitted, and they have no owner-decision record in the repo. So `rankings.json` is **not** a contract result, and neither R2 nor any interpretation should use it.
- **The D11 entry has four problems:**
  1. It states that the exclusion "was approved by the project owner before any re-ranked number was published". There is no such decision in `sprint-3-verification.md` or in this session.
  2. It quotes typed outcome figures (auto session conversion "0.0369 to 0.0376", category-sessions "264,065 to 258,936"), against CLAUDE.md rule 1.
  3. It was derived from run 3 results that were read before any H4 brief.
  4. The pandas audit of the raw file breaks the "DuckDB for anything over the raw data" rule, and none of the exploration is in the search log.
- **Who made these changes isn't known from the files.** No other Claude session is running on this machine now (checked with the agent list). The owner needs to establish it.

## 2. Fired rules (run 4, from its log only)

From the log's last line:
- **Top level:** F1, F3, F5, F6, F8.
- **Code level:** F1, F5, F6, F8.
- **Not fired:** F2 and F7, at both levels.

The rule values themselves are in `rankings.json`, which hasn't been opened, and they're from the non-contract pipeline anyway. What follows is a diagnosis of **why each rule would fire**, from the method and from synthetic data. No real-data result is used.

### F6 (negative control): a flaw in the method, not a code bug and not the permutation design

**Question:** does the procedure separate categories when the null is true? And if so, is the cause (a) a code bug, (b) the negative control's design (labels permuted across category-sessions while the bootstrap resamples users), or (c) the separability rule itself?

**Method:**
- **Synthetic datasets:** 13 categories with sizes from 1,500 to 60,000 category-sessions, all with the same expected conversion (4%). No real data was read.
- **Procedure:** the committed `funnel.rankings` functions, run exactly as C1 runs them: maximum-likelihood prior refitted per resample, user bootstrap, seed 20260926, 90% rank intervals, separable = non-overlapping.
- **Scripts:** in the session scratchpad, not the repository.

**Results (code output):**

| Synthetic null | Clustering | Resamples | Datasets with ≥ 1 separable pair (procedure on the data as generated) | After the C9 session-level permutation | After a user-level permutation |
|---|---|---|---|---|---|
| S1: independent sessions (1 per user) | none | **2,000** (the real setting) | **3 of 6** (5, 3, and 3 pairs of 78) | not run at 2,000 | not run at 2,000 |
| S1 | none | 200 | 8 of 12 | 6 of 12 | 3 of 12 |
| S2: heavy-tailed sessions per user, spread across categories | across categories | 200 | 7 of 12 | 7 of 12 | 6 of 12 |
| S3: heavy-tailed users tied to one category | within categories | 200 | 7 of 12 | 6 of 12 | 5 of 12 |

At 2,000 resamples, dataset by dataset (S1):

| Dataset | Separable pairs | Largest \|z\| of a raw rate vs the pooled rate | Fitted prior precision s |
|---|---|---|---|
| 0 | 0 | 2.56 | 3.11e8 |
| 1 | 5 | 2.38 | 4.37e4 |
| 2 | 0 | 2.49 | 9.27e7 |
| 3 | 3 | 2.51 | 8.33e4 |
| 4 | 3 | 2.46 | 4.93e4 |
| 5 | 0 | 1.33 | 1e10 (the cap) |

**Reading:**
1. **Not the permutation design.** S1 has no clustering and no permutation, and it still separates in half the datasets at the real settings. Changing the permutation unit (session or user) doesn't bring the rate near zero in any scenario.
2. **The separability rule is miscalibrated under ties.** With 13 equal categories, chance extremes (|z| ≈ 2.4–2.6, which is ordinary for the largest of 13) get rank intervals at opposite ends. Percentile bootstrap intervals for ranks are known to be unreliable when the true parameters are tied or nearly tied: the bootstrap reproduces the observed chance ordering instead of the uncertainty about it. False separations appear in exactly the datasets where the prior fit finds spurious spread (s ≈ 4–8 × 10⁴, so estimates stay close to the raw rates). They don't appear where it correctly finds almost none (s ≥ 10⁸, so every estimate is near the pooled rate).
3. **No sign of a code bug.** The unit tests check the numerics, the resampling, the ranks, and the separability logic against hand counts. The pre-run calibration (search-log row 36) already showed separation under identical rates at a lower rate with 4 categories, and that rate grows with the number of categories. What rules a bug out is the direction of the evidence: the failure appears without any permutation, in the simplest null. A bug in the permutation code can't cause that. A bug in the ranking core can't be fully excluded by this diagnostic, but R2 (an independent implementation) would catch one in the estimates and point ranks.
4. **A correction to my own diagnostic:** a Bonferroni pairwise comparison I added at 200 resamples was meaningless (with 200 draws, the adjusted quantiles are just the minimum and maximum), so it's excluded. The rejected alternative F was not computed on real data.

**Implication:** as specified, the rule "different only where 90% rank intervals don't overlap" will describe chance differences as real in a large share of null situations. That is exactly the claim the ceiling was written to prevent. The negative control did its job.

### F3 (clustering; top level): expected, and it undercuts the amount of shrinkage

**What the rule means:** a median design effect above 2 means that user clustering makes the real sampling variance of a category's rate more than twice the binomial variance the prior uses.

**Consequence:** the posterior means shrink too little, because they're computed with the nominal n and not the effective n. The bootstrap intervals include the clustering, so the rule concerns the point estimates. The synthetic S3 scenario shows design effects of about 6 when users are tied to categories.

**The record's pre-stated fix:** divide n by the design effect (effective n). It's "not pre-approved" and needs H3.

### F1 (single prior; both levels): the rule is miscalibrated for large categories

**What the rule means:** a leave-one-out prior mean shift larger than the category's own interval width.

**Why it fires anyway:**
- At the top level, intervals are very narrow (millions of category-sessions). So nearly any category whose rate differs from the others moves the prior mean by more than its own interval width, even when a single prior is perfectly reasonable.
- The objections at Step 1 anticipated this: shrinkage barely matters at the top level. The comparison measures size, not whether the prior is appropriate.

**Better diagnostic (proposed):** compare the shift with the spread of the prior (for example, the prior's standard deviation), or test bimodality directly.

### F5 (B and C disagree; both levels): a symptom of the same instability

**What the rule means:** the Wilson ranking (C) and the empirical-Bayes ranking (B) are bootstrapped with the same resamples and compared with the same rank-interval rule.

**Why it fires:** if that rule is unstable near ties (F6), two nearly equivalent orderings will disagree on which near-tied pairs separate. The disagreement doesn't show that B or C is wrong. It shows that separability is fragile.

### F8 (sensitivity movement; both levels): also consistent with fragile separability

**What the rule means:** a rank change of more than 2 places among common categories, or a changed separable status, under C5 (minimum size) or C8 (no missing-code sessions).

**Why it fires:**
- The separable-status part inherits the F6 fragility.
- The rank-move part may be real, especially at the code level where small codes enter at size 500. It can only be read from `rankings.json`, after the pipeline question is settled.

## 3. Options for the owner

**First, decide the pipeline state. Each option below assumes it's settled.**
- **(P1)** Revert the uncommitted staging and contract changes to the committed `015a80f` state, rebuild the marts through `funnel.build` (gated and recorded), and treat run 4 as void (search-log row: "run on a non-contract pipeline; not used").
- **(P2)** Adopt a bot exclusion properly: an H3 decision on a Changes entry written without typed numbers; the `assert_dedup_reconciles` failure resolved; the exploration logged in the search log (it's exploratory, and it was done after outcomes were seen); then a gated rebuild. Note that choosing the exclusion **after** seeing a ranking is a post-hoc specification change, and the false-discovery gate has to count it.

**Then, for the ranking:**

| Option | What it publishes | What it needs | Cost | Risk |
|---|---|---|---|---|
| **A. An honest "not reliably distinguishable" result** | Each category's session conversion with counts and user-clustered intervals, in a table, and a plain statement: "The pre-specified method for telling categories apart failed its own negative control (it separates categories that are identical by construction), so this page doesn't rank categories or call any two different." No ordering claim | H3 for the claim wording and a deviation entry (the separability rule withdrawn); H9 on the page | Low. The counts and intervals already exist in the method; a rerun on the settled pipeline without separability claims | Low. It says less, and it's true |
| **B. A calibrated replacement rule, then rerun** | A ranking with differences claimed only under a rule that passes a synthetic null calibration **before** real data (target: at most about 10% of null datasets with any false separation at 13 and at 117 categories). For example: simultaneous intervals for pairwise differences by a max-statistic bootstrap, or posterior probabilities of rank from a hierarchical model with the clustering handled | H3 for a new method record and Changes entry; a calibration study committed before any real run; F1 and F3 redesigned | High. New code, calibration, and 4+ hours of compute per real run | Medium. A second method chosen after the first failed has to be counted by the false-discovery gate |
| **C. Top level only, descriptive** | 13 category rates with clustered intervals and an effective-n note (F3); no code level, no ranking | H3 (scope change from C-D1) | Low | Low; drops the drill-down |
| **D. Stop the ranking in Sprint 3** | Nothing on rankings; the Sprint 3 effort moves to Step 8's framing documents, with this brief as the finding "size-adjusted separation isn't supported by a calibrated method here" | H1 (scope) | Lowest | Low; the Sprint 3 deliverable changes |

**Executor recommendation:**
1. **P1 first:** restore the contract state; reconsider any bot exclusion separately and prospectively.
2. **Then A:** it's the only option that can be published honestly without new methodology, and it directly answers "which categories can we tell apart?" with "not reliably, by the pre-specified method".
3. **B as a later sprint,** if a ranking is still wanted.

## 4. What stays pending

- **Nothing is published, and nothing is committed:** this brief is in the working tree only, next to the uncommitted changes described in §1.
- **R2 is not run.** `rankings.json` is not opened.
- **H4:** the pipeline decision (P1 or P2) and the ranking option (A–D).
- **Owner fact-finding:** who ran the audit scripts, edited the staging models and the contract, rebuilt the marts outside `funnel.build`, and started run 4; and whether the "approved by the project owner" sentence in the D11 entry reflects a real decision.

## 5. Owner decision (H4, 2026-09-27) and the quarantine record

**Decision (owner's words):** "the 06:57–07:35 changes, including the D11 entry, were not made or approved by me; the 'approved by the project owner' sentence is false. Pipeline: P1 with quarantine […] Ranking: option A […]" (recorded in full in `ai-workflow/sprint-3-verification.md`).

**Quarantine branch:** `quarantine/unapproved-2026-09-27`, commit `884cae3`, pushed to origin, based on `015a80f`. It must never be merged. The commit holds the working tree exactly as found at 12:07; this brief was excluded from it as instructed. pytest on that tree: `212 passed (pytest_exit_code=0)`.

| Path | What it is |
|---|---|
| `analysis/auto_audit.py` (created 06:57) | pandas audit of auto-category conversion at several session-count thresholds, over the full Parquet file |
| `analysis/auto_bot_exclusion.py` (07:02) | pandas recomputation of auto-category conversion without user 512475445 |
| `pipeline/models/staging/stg_events.sql` (07:07) | `where user_id != 512475445` before deduplication |
| `pipeline/models/staging/stg_dedup_audit.sql` (07:34) | the same filter on the raw-row audit |
| `docs/metrics.md`, `web/content/metrics.md` (07:12) | Changes entry "2026-09-27 · Bot exclusion at source (Section 2, D11)", with typed outcome figures and a false approval claim |
| `ai-workflow/evidence/sprint-3/rankings.json` (11:40) | run 4's output, on marts rebuilt outside `funnel.build`; not a contract result |

**Not in git (gitignored, left in place under `data\`):** `dbt_rebuild_run3_botfix.log`, `dbt_test_run3_botfix.log`, `rankings_run4.log`, and run 4's partial files in `rankings_partial\`. The rebuilt warehouse itself is replaced by the gated rebuild.

**Restored state:** `sprint-3/step4-rankings` at `015a80f`. Its staging models equal `main`'s, and the quarantined files are absent from the working tree.

**Guards added (`funnel.provenance`):**
- `funnel.build` and `funnel.rankings` refuse a dirty working tree.
- `funnel.build` records the ranking marts' fingerprint after a successful gated build.
- `funnel.rankings` refuses marts whose fingerprint has no gated build record (clean tree at start and end, dbt exit 0, every expected test run).

One reading was needed: `funnel.build` can't be required to find its own output's fingerprint in an earlier record, because it creates that record. So only the dirty-tree guard applies to `funnel.build`. Proposed but not done: the same fingerprint guard for `funnel.verify` and `funnel.export`, which also read the marts.
