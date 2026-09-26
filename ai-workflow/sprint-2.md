# E-commerce Funnel Analytics — Sprint 2: Governed Tier, Discrepancy Investigation, Purchases in Later Sessions

Before doing anything, read these: `CLAUDE.md`, `docs/metrics.md` (including all Changes entries), `ai-workflow/sprint-1-verification.md`, `ai-workflow/correction-log.md`, and `ai-workflow/claim-ledger.md`. This sprint runs under **trio-sprint-workflow v2.3+** and **verified-analytics-project v2.1+**. Read their human-in-the-loop, uncertainty, documentation, and gates references.

**Goal:** Move the project to the Governed tier. Then explain the two largest open questions in the Sprint 1 numbers:
- **(A)** why the two revenue figures differ;
- **(B)** how much carted value with no observed purchase in the session was purchased by the same user in a later session.

**Risk:** moderate complexity. **Epistemic risk is consequential** for B. The full loop applies: method challenge, search log, R2 and R3, negative controls, adversarial review, and H9 sign-off.

**Out of scope:** recommendations, size-adjusted category rankings, Tableau, the agent (these are Sprints 3–4). The home page's "What the data shows" section stays unchanged.

Stop and escalate per the uncertainty protocol. Low-impact assumptions go in the report. Material or critical ones get an escalation brief.

## Human checkpoints in this sprint

| Checkpoint | Step | What the owner decides |
|---|---|---|
| H6 | 1 | Branch protection and Copilot review settings (exact settings presented; the owner applies or approves) |
| H2 | 2 | Method-selection records for A and B, including the proposed follow-up window and the case list |
| H3 | 3 | The Changes entry defining the new metrics |
| H4 | any | Escalations |
| H8 | 1, 7 | Merging each PR |
| H9 | 7 | Signing off new claim-ledger rows |

The executor stops at each checkpoint, presents a one-line decision, and waits.

## Step 0 — Preflight and adopting v2

1. Preflight: runtimes, CLIs, `gh auth status`, free disk, available memory (gate at 3 GB before heavy runs).
2. Create `ai-workflow/tools.md` from the trio template. Fill it with the verified versions, the Vercel project and production domain, the data source, machine constraints, and the tool selection guide.
3. Create `ai-workflow/uncertainty-register.md` and `ai-workflow/search-log.md` from the templates, and the folder `ai-workflow/method-selection/`.
4. Documentation baseline:
   - Add a `.env.example` that lists `KAGGLE_API_TOKEN` (name and description only).
   - Add an env-drift test.
   - Add a `CHANGELOG.md` with v1.0.0 and v1.0.1 reconstructed from the tags, plus an `Unreleased` section.
   - Update the README's "How this was built" section so it points to where the owner's decisions are recorded: the metrics Changes entries, the claim-ledger sign-offs, the correction log, and (from now on) PR approvals.
5. Update the tier line in `CLAUDE.md` to: "Tier: Governed (from Sprint 2): branch → PR → CI → Copilot review (if available) → owner merge. Never push to main directly."
6. Commit this step directly to `main`. It's the last direct commit. Gate it on pytest and push it.

## Step 1 — Governed-tier setup

1. Add `.github/workflows/ci.yml`, adapted from the trio template:
   - pytest on committed exports and synthetic fixtures (**no** raw data or dbt builds in CI);
   - web lint and build;
   - the docs checks (link check).

   Add `.github/pull_request_template.md` from the template.
2. **Copilot:** determine whether Copilot code review is available on this account (check with `gh` or the repo settings; don't guess). Record the result in `tools.md`.
3. **H6: branch protection.** Present the exact settings for `main`:
   - a PR is required;
   - the CI status checks must pass;
   - branches must be up to date before merging;
   - no force pushes and no deletion;
   - Copilot review, if available.

   Give the owner the exact UI path or `gh` command, and stop. The owner applies the settings, or approves the executor applying them.
4. Deliver Step 1 itself as the first PR (branch `sprint-2/governed-setup`). Wait for CI to pass, address Copilot's comments if it's available, then **stop for the owner's merge (H8)**.

From here on, all work goes on `sprint-2/<name>` branches, through PRs.

## Step 2 — Method selection (H2)

Write `ai-workflow/method-selection/A-revenue-gap.md` and `B-later-purchases.md` from the template. Commit both on a branch, then stop for H2.

**A. The revenue gap (proposed):**
- **Question:** "Why are there two revenue figures?"
- **Question type:** descriptive and diagnostic.
- **Estimand:** the gap between primary and collapsed revenue, decomposed over repeated same-product purchase events within a session, by:
  - time between repeats (the same second, under a minute, a minute or more);
  - whether the price is identical;
  - top-level category;
  - repeats per pair.
- **Claim ceiling:** patterns *consistent with* repeated logging versus multiple units. **We can't establish which**, because there's no quantity field.
- **Secondary cases:** the 30,220 exact duplicate rows, and the raw-versus-contract gap in cart events with no prior view.
- **Candidate methods:** (1) a decomposition table; (2) a distribution of time between repeats with a threshold sensitivity check. State which is rejected and why.

**B. Later purchases (proposed):**
- **Question:** "Of carted value with no observed purchase in the session, how much did the same user purchase in a later session?"
- **Question type:** descriptive and longitudinal, **not causal**.
- **Estimand:** among carted (session, product) pairs with no purchase of that product in the session, the share (count and value) followed by a purchase of the same product by the same `user_id` in a **later session**, within a **7-day follow-up window** from the cart session's start.
- **Right-censoring guard:** include only pairs from sessions that **start by October 24, 2019, 23:59:59 UTC**, so every included pair has a full 7 days of follow-up. Sensitivity windows: 3 and 14 days, each with its own matching cutoff.
- **R3:** a Kaplan–Meier curve of time to later purchase, using all pairs with censoring at the end of the data. Its 7-day value should agree with the fixed-window estimate within its interval.
- **Negative control:** for the same eligible sessions, the share of products **viewed but not carted** that the same user purchased within the same window. This separates a cart-specific pattern from general return-shopping.
- **Data check:** how reliable `user_id` is. Are there missing values? Do any sessions span multiple users? Record the share of eligible pairs with a usable `user_id`.
- **Claim ceiling:** "N% of this carted value was followed by a same-user purchase of the product within 7 days." It **can't** support "the cart caused the purchase" or anything about loss.
- **Uncertainty:** a bootstrap CI over users (clustered, since a user can have many pairs).

**Stop for H2.** The owner approves, edits, or rejects each record, including the window, the cutoff, and the case list.

## Step 3 — Changes entry (H3)

Draft one dated Changes entry in `docs/metrics.md` that defines every new metric used by A and B:
- exact numerators, denominators, populations, windows, and cutoffs;
- display labels and short labels;
- claim-tier wording.

The display labels must follow the naming rules. For example: "carted products purchased by the same user in a later session within 7 days", never "recovered". **Stop for H3.** After approval, commit it **before** computing anything.

## Step 4 — Analysis A

1. Build the marts and exports for the decomposition and the secondary cases (RAM gate before heavy runs; `threads: 1`). Log every cut you try in `search-log.md`.
2. Write reconciliation tests: the decomposition sums exactly to the gap, and the secondary-case counts match the Sprint 0 and Sprint 1 figures on the stated bases.
3. Add **R2:** `funnel.verify` recomputes the gap decomposition independently of dbt.
4. Write claim-ledger rows (tier matching the evidence; A is at most "shows" for the patterns, and never "establishes" which explanation is true).

## Step 5 — Analysis B

1. Run the main estimate, the sensitivity windows, the negative control, and the `user_id` reliability check. Every run goes in `search-log.md`, including runs that aren't reported.
2. Add **R2:** `funnel.verify` independently recomputes the 7-day share (count and value).
3. Add **R3:** the Kaplan–Meier estimate. Report whether it agrees with the fixed-window estimate.
4. **Slow-down trigger:** if the share is surprisingly high or low, or R2, R3, and the negative control disagree, stop and write an escalation brief before interpreting anything.
5. Run the **adversarial review** (verified-analytics-project `adversarial-review.md`). Record the attacks tried and their outcomes: identity linking, censoring, bot-like users, multiple carts of the same product, purchases of the same product by other users in the same household (can't be observed; state it as a limitation).
6. Write claim-ledger rows at the tier the evidence supports.

## Step 6 — Site

1. Add `/investigations` with two pages:
   - "Why are there two revenue figures?" (A, written as a stakeholder answer);
   - "Were carted products purchased in a later session?" (B).

   Each page states its question, its answer at the ledger tier, the evidence with Sources lines, the method (linking to its method-selection record), the limitations, and the claim ceiling in plain words.
2. Charts: the gap decomposition; the time-between-repeats distribution; the Kaplan–Meier curve with its interval; a comparison of the negative control with the main estimate.
3. Add a link from the home page's "Where to look next" section. **Don't** change the "What the data shows" section.
4. Update `/data` and `/metrics` as needed. Naming rules, sourced-sentence rules, and the 390 px checks all apply.

## Step 7 — Documentation, release, sign-off

1. Complete the documentation cadence:
   - `CHANGELOG` Unreleased entries;
   - the README status line;
   - `tools.md`, if changed;
   - an uncertainty-register review;
   - `ai-workflow/sprint-2-verification.md`, which records every owner decision this sprint with its artifact;
   - correction-log entries.
2. Open the release PR. Wait for CI and Copilot. **Stop for the owner's merge (H8).**
3. After the merge: deploy from `main`, run smoke against production (add the new pages to smoke), take screenshots, and tag **v1.1.0** after smoke passes. Move `Unreleased` into a versioned `CHANGELOG` entry.
4. **Stop for H9:** the owner checks the live investigation pages and signs off the new claim-ledger rows (date, the rows, the pages checked).

## Definition of Done

- [ ] Governed tier active: CI green, branch protection on (H6), Copilot status recorded; every change after Step 0 merged by the owner through a PR (H8)
- [ ] Method-selection records approved (H2), and the Changes entry approved and committed before computation (H3)
- [ ] A: the decomposition reconciles exactly to the gap; R2 matches; secondary cases reconcile; the claim ceiling is stated on the page
- [ ] B: the censoring-safe estimate, sensitivity windows, R2 match, R3 agreement reported, negative control reported, `user_id` reliability reported, adversarial review recorded
- [ ] Search log complete, including unreported runs; the claim ledger has rows for every new published claim
- [ ] Correctness level stated for each claim; no open **critical** item in the uncertainty register
- [ ] Documentation cadence met: `.env.example` with the drift test, `CHANGELOG`, README, `tools.md`, verification file; drift checks pass
- [ ] Deployed; production smoke passes; tagged v1.1.0; H9 sign-off recorded

## Final report

The report must include:
- the PRs, commits, and SHAs;
- the CI, dbt, pytest, verify, and smoke output, verbatim;
- the A decomposition table;
- the B estimates: main, sensitivity windows, Kaplan–Meier, the negative control, and the `user_id` check;
- the adversarial review's outcomes;
- the claim-ledger rows as written;
- the owner decisions recorded;
- correction-log entries;
- the open uncertainties;
- anything that needs a decision.
