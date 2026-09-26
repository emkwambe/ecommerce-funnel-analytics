# Method Selection — A. Why are there two revenue figures?

Template: verified-analytics-project v2.1 (`assets/templates/method-selection.md`). Written in Sprint 2 Step 2 (2026-09-26), before any Sprint 2 quantity is computed. No outcome in this record comes from a new query: the structural facts cited are from the committed Sprint 0 profile (`docs/data-profile.md`) and the Sprint 1 tests. **Status: draft for the owner's decision (H2).**

**Question:** "Why are there two revenue figures?" (the site shows revenue, primary, and revenue with repeat purchase events collapsed, `docs/metrics.md` §4).

**Question type:** descriptive and diagnostic. It describes where the gap sits; it does not estimate a cause.

**Decision supported:** which revenue figure a stakeholder should quote for which purpose, and whether the repeat pattern is worth raising with the data publisher. It supports no decision about customers.

**Estimand:** the revenue gap, G = revenue (primary) − revenue with repeat purchase events collapsed, over valid sessions in October 2019 (UTC). By the §4 definitions, G is exactly the sum of the prices of **surplus purchase events**: every purchase event in a (session, product) pair other than one event at the pair's earliest purchase timestamp. G is decomposed over the surplus events, each placed in exactly one cell of each dimension:

1. **Time since the pair's previous purchase event:** the same second (0 s), under a minute (1–59 s), a minute or more. "Previous" means the latest other purchase event of the pair at or before this one, so tied timestamps give 0 s with no ordering choice.
2. **Price compared with the pair's earliest purchase price:** identical or different. The earliest price is the one the collapsed figure keeps. The Sprint 1 test `assert_no_tied_earliest_purchase_price` guarantees it is unique. "Compared with the preceding event" is not used: events tied at a later timestamp can differ in price, so "preceding" would need an ordering the data does not have.
3. **Top-level category** of the surplus event (`category_top`, "unknown" for missing codes).
4. **Purchase events in the pair:** 2, 3, 4 or more.

Plus the two-way table of dimensions 1 × 2, the combination most directly related to the two readings.

**Unit:** surplus purchase events (counts) and their price sum (value), with the pairs that have them.

**Claim ceiling:** the decomposition **shows** where the gap sits. Patterns can be described as *consistent with* repeated logging (for example, identical price within seconds) or *consistent with* multiple units (for example, repeats minutes apart). **Which explanation is true cannot be established**: the file has no quantity column and no order or transaction ID (uncertainty register U1).

## Secondary cases (proposed case list)

| Case | What is decomposed | Reconciles to |
|---|---|---|
| A-S1. Exact duplicate rows | The exact-duplicate surplus rows removed by D1 (`docs/metrics.md` §2), by event type, and by duplicate-group size (2, 3, 4 or more rows). | The removed count in `mart_data_quality` and the Sprint 0 raw-basis figure (`funnel.verify` already matches both). |
| A-S1v. *(optional; needs your decision)* Value of the removed duplicate purchase rows | The price sum of exact-duplicate purchase rows removed by D1. This is a third revenue-like quantity (before deduplication), not defined in the contract. | The raw purchase-price sum minus revenue (primary), after also accounting for purchase events in excluded sessions. |
| A-S2. Cart events with no view at or before them: raw basis vs contract basis | The difference between the Sprint 0 raw-basis count and the Sprint 1 contract-basis count, split into: removed as exact duplicates; in null-session events; in multi-user sessions; any remainder. | Both published counts exactly. A non-zero unexplained remainder stops the step with an escalation. |

## Data-generating process (relevant features)

- **Logging, not orders.** Each row is a logged event. The publisher states that multiple purchase events in a session form one order (§4), but nothing marks units. A repeated purchase event can be a second unit, a re-sent tracking call, a page reload, or a split payment. None of these is observable.
- **Deduplication shapes the time dimension.** D1 already removed exact duplicate rows, so an identical repeat in the same second survives only if some other column differs. The Sprint 0 profile found few same-second repeat pairs on the raw basis (`docs/data-profile.md`, D4 evidence). The "same second" cell will therefore be small by construction. That describes the pipeline, not customer behavior, and the page must say so.
- **Second resolution.** No event has sub-second precision (profile), so 0 s means the same logged second, not simultaneity.
- **Price can change between events.** A different price on a repeat can be a price change, a different variant under one `product_id`, or a logging artifact.
- **Clustering.** Surplus events cluster within pairs, sessions, and users; a few heavy pairs could dominate a cell. Dimension 4 and the diagnostics below expose that.

## Candidate methods

| Method | Assumptions | Verifiable how? | Fits this data-generating process? | Verdict |
|---|---|---|---|---|
| (1) Exact decomposition table of G over the four dimensions and the 1 × 2 table | Each surplus event is assigned to exactly one cell per dimension; G equals the sum of surplus prices | Reconciliation test: each dimension's cells sum exactly (DECIMAL) to G; R2 in `funnel.verify` | Yes: purely descriptive, no model, no independence assumption | **chosen (primary)** |
| (2) Distribution of the time since the previous purchase event, with a threshold sensitivity | The cut-offs in (1) are arbitrary; a distribution shows whether the result depends on them | The cumulative share of G within thresholds of 0 s, 1 s, 5 s, 10 s, 30 s, 60 s, 5 min, 30 min, and 1 h (fixed now, before viewing) | Yes | **chosen (supporting)**: it tests the robustness of the three bins in (1) rather than replacing them |
| (3) A rule that labels each repeat as "logging" or "extra unit" (for example, identical price within N seconds = logging) and reports "true revenue" | That the rule identifies the mechanism | Not verifiable: there is no ground truth in the file | No | **rejected**: it turns an unobservable mechanism into a published number, above the claim ceiling, and it would define a new revenue figure outside the contract |
| (4) Latent-class or mixture model of repeat timing | The timing distribution is a mixture of two identifiable processes | Only by model fit, not by ground truth | Weak: identification rests on distributional assumptions no data here can check | **rejected**: added complexity without the ability to validate; it still could not establish the mechanism |

The brief lists (1) and (2) as the candidates and asks which is rejected. **This record proposes keeping both** (primary and supporting) and rejecting (3) and (4), because (2) checks (1)'s arbitrary cut-offs rather than competing with it. See decision A-D3.

## Failure conditions

- **The decomposition does not sum exactly to G:** the definition of surplus events differs from §4 as built. Detected by the reconciliation test, which fails the build.
- **G ≠ published primary − collapsed revenue:** a population mismatch (sessions, deduplication). Detected by a test against `kpis.json` and the marts.
- **One pair or user dominates a cell:** the cell describes one case, not a pattern. Diagnostic: the share of each cell's value from its top 10 pairs, reported beside the table.
- **Conclusions depend on the bin edges:** the threshold sensitivity (2) shows it. The wording then drops the bin-based pattern.
- **The "unknown" category holds a large share of G:** the category dimension is then uninformative for that share, and it is disclosed.

## Robustness plan

- **R1:** rerun from a clean tree (the build record).
- **R2:** `funnel.verify` recomputes G and every cell of dimensions 1–4 from the Parquet file with separately written SQL, with no dbt models, and requires exact matches.
- **R3:** not required at this risk level (material, descriptive). The threshold sensitivity (2) is the alternative-specification check.
- **Falsification / controls:** no mechanism is claimed, so no negative control. As a consistency check, the surplus events per pair from the Sprint 0 profile (raw basis) and the contract-basis figure are reconciled, with the difference explained by deduplication and session exclusions.
- **Search log:** every cut computed, including any not published, is logged before it is viewed.

## Decisions needed (H2)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| A-D1 | Price dimension baseline | (a) the pair's earliest purchase price; (b) the preceding event's price (ambiguous under later ties) | **(a)** |
| A-D2 | Time bins | (a) as proposed: 0 s, 1–59 s, ≥ 60 s; (b) add a fourth bin (≥ 1 h) | **(a)**, with the threshold sensitivity giving the finer view |
| A-D3 | Candidate methods | (a) keep (1) as primary and (2) as supporting, reject (3) and (4); (b) use (1) only and reject (2) | **(a)** |
| A-D4 | Secondary case list | Approve A-S1 and A-S2; include or drop A-S1v (a new revenue-like quantity, which then needs its own Changes entry) | **Approve A-S1 and A-S2; drop A-S1v.** It widens the question from two revenue figures to three |
| A-D5 | Claim ceiling | As written above | **Approve** |
