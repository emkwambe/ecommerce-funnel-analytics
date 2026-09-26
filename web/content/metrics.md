# Metric Definitions

**Owner:** Eddy Mkwambe
**Status:** Locked once committed. Changes only through a dated entry in the Changes section at the end, giving the reason and the effect on published numbers.

This document is the contract for every number on the site, in Tableau, and in answers from the "Ask the data" agent. A metric not defined here may not be published or answered. The agent must decline questions that need an undefined metric.

Evidence counts cited below come from the Sprint 0 structural profile: `docs/data-profile.md`, dataset SHA-256 `fedd9384…5b80`, October 2019, 42,448,764 raw rows.

## 1. Naming rules

Labels describe what the data shows, never inferred customer intent.

1. **Cart events are not carts.** A cart event is a logged add-to-cart action, and one product can be carted repeatedly. Say "observed cart events" or "sessions with an observed cart event". Never say "carts" or "unique carts".
2. **No purchase is not abandonment.** A cart event with no later purchase in the session does not prove the customer abandoned. They may have bought in another session, on another device, or not at all. Say "no observed purchase in this session".
3. **No inferred loss.** Do not use "abandoned", "abandonment", "lost revenue", "lost sales", "recoverable revenue", "leak", "drop-off", "lost cart", or "lost carts" as a statement of customer behavior. Say "carted value with no observed purchase in this session". Any estimate of what could change is a labeled scenario (Section 8), never a finding.
4. **Observed means logged.** "Observed" means present in this October 2019 log after the rules in Section 2. Absence from the log is not evidence of absence in reality.
5. **Time is UTC.** The store's local time zone is unknown. Every day or hour label says UTC, and no hour-of-day result is described as customer local behavior.

A test fails if any file under `web/`, `docs/` (except this section), or any published export contains a prohibited term from rule 3, or the whole word "carts" anywhere (which also covers "unique carts"), matching rule 1.

## 2. Event rules (decisions D1–D3, D6, D9, D10)

- **D1. Deduplication.** Exact duplicate rows are removed; the evidence is 30,220 surplus rows in 18,099 groups. The one near-duplicate group whose rows differ in another column is kept as logged. The removed count is published as a data-quality metric.
- **D2. Zero prices.** Zero-price events (68,673; none of them purchases) count as events. They are excluded from every value calculation and published as a data-quality count.
- **D3. Price.** Revenue uses the price logged on each purchase event. Carted value follows the pair-level rule in Section 7: the latest non-zero cart price of each (session, product) pair.
- **D6. Cart event order.** Cart events count regardless of whether a view preceded them in the session. Cart events with no view at or before them (4,655) are published as a data-quality count.
- **D9. Event types.** Only view, cart, and purchase exist in this file, and all three are used.
- **D10. Time.** Timestamps are UTC as logged. No events fall outside October 2019 UTC.

## 3. Session rules (decision D8)

- A **session** is `user_session` as logged.
- **Excluded from session metrics:**
  - events with a null `user_session` (2);
  - sessions containing more than one `user_id` (348).

  Both counts are published as data-quality metrics.
- **Kept:** sessions spanning more than 24 hours (17,086). As a sensitivity check, these metrics are also published with those sessions excluded: session purchase rate, view-to-cart session rate, cart-session purchase rate, revenue per session, and average order value.
- **Valid session:** a session remaining after the exclusions, with at least one event after deduplication.

## 4. Order and revenue (decision D4)

- **Order.** One valid session with at least one purchase event. This follows the publisher's statement that multiple purchase events in a session form a single order. Orders = sessions with an observed purchase.
- **Revenue (primary).** The sum of `price` over deduplicated purchase events in valid sessions.
- **Revenue, repeat purchase events collapsed (secondary).** The sum over distinct (session, product) purchase pairs of the price on the earliest purchase event of each pair. Repeated purchase events of the same product in a session may be extra units or repeated logging, and the data can't tell which. The evidence is 41,406 pairs with repeats and 52,477 surplus events. The primary and secondary figures are always shown together wherever the difference is discussed.
- **Average order value.** Revenue ÷ orders.
- **Revenue per session.** Revenue ÷ valid sessions.

## 5. Purchase paths (decision D5)

Each purchase event is classified by whether its product has a cart event anywhere in the same session:

- **"Purchase with an observed same-session cart event"**
- **"Purchase with no observed same-session cart event"**

Evidence: 406,639 of 742,849 purchase events have no same-session cart event.

Published per path: purchase event counts, revenue, and revenue share. Totals include both paths. Whether no-cart purchases had cart events in earlier sessions of the same user is an analysis question (Section 9), not part of this definition.

## 6. Funnel metrics (session grain)

All metrics here use valid sessions:

| Metric | Definition | Display label |
|---|---|---|
| Sessions | Count of valid sessions | Sessions |
| Sessions with a view | Valid sessions with ≥1 view event | Sessions with an observed view |
| Sessions with an observed cart event | Valid sessions with ≥1 cart event | Sessions with an observed cart event |
| Sessions with a purchase | Valid sessions with ≥1 purchase event | Sessions with an observed purchase |
| Session purchase rate | Sessions with a purchase ÷ sessions | Sessions with an observed purchase (%) |
| View-to-cart session rate | Sessions with a view and ≥1 cart event ÷ sessions with a view | Viewing sessions with an observed cart event (%) |
| Cart-session purchase rate | Sessions with ≥1 cart event and ≥1 purchase of a product carted in that session ÷ sessions with ≥1 cart event | Sessions with an observed cart event and an observed purchase of a carted product (%) |
| Cart sessions with no observed purchase | Sessions with ≥1 cart event and no purchase event of any product | Sessions with an observed cart event and no observed purchase in this session |

## 7. Carted value

Carted value is measured at (session, product) pair grain, so repeated cart events of one product are not double-counted:

- **Carted pairs.** Distinct (session, product) pairs with ≥1 cart event in a valid session.
- **Carted value with no observed purchase in this session.** The sum, over carted pairs with no purchase event for that product in the session, of the pair's latest non-zero cart price: the price on the latest cart event of the pair whose price is above zero.
- **Zero-price carted pairs.** Carted pairs whose cart events are all zero-price count in pair counts but are excluded from every value. Their count is published as a data-quality metric.
- **Population and category.** Carted value with no observed purchase in this session covers all carted pairs in valid sessions, with no view requirement. It is grouped by the category on the pair's latest cart event. This population differs from the category funnel's (Section 9), and the funnel page discloses the difference.
- **Observed cart event count.** The raw count of deduplicated cart events, always labeled as cart events.

## 8. Scenario estimates (not yet defined)

The business question asks what to test first. Any "what if" quantity must be added through a Changes entry before use. Examples would be carted value that a higher cart-session purchase rate might represent, or a gap to a benchmark rate. Such an entry must state the formula, its assumptions, and the label "scenario estimate, not an observed amount". No scenario estimate appears anywhere until defined here.

## 9. Breakdowns (decision D7)

- **Category.**
  - Headline views use the top-level segment of `category_code` (the text before the first dot). Drill-downs use the full `category_code`.
  - Missing codes form an explicit **"unknown"** level. Evidence: 13,515,609 events.
  - Every category view states the unknown share of events and of revenue.
  - 55 codes map to more than one `category_id`. Grouping by code merges those ids; this is disclosed on category pages.
- **Brand.** Same treatment, with an explicit "unknown" level (evidence: 6,113,008 events) and a stated unknown share.
- **Category funnel grain.** A (session, top-level category) pair enters the category funnel when the session has ≥1 view in that category. Cart and purchase steps count only events in that category within the session. The same session can appear in several category funnels, and this is disclosed.
- **Time.** Day and hour of day, both labeled UTC.
  - Daily KPIs assign each session, its order, and its revenue to the UTC day of the session's first event, labeled "UTC day of session start".
- **Permitted analysis questions** beyond fixed metrics, labeled exploratory: whether no-cart purchases had cart events in an earlier session of the same `user_id`, and how rates vary by price band.

## 10. Data-quality metrics (always published)

Every data-quality metric states its basis. Exact duplicate rows removed are counted on raw rows. All other data-quality metrics are counted on deduplicated events in valid sessions. Where Sprint 0 published a raw-basis figure for the same check, it is shown alongside. Comparisons with the Sprint 0 profile compare figures on the same basis.

- exact duplicate rows removed;
- zero-price events;
- cart events with no view at or before them in the session;
- null-session events excluded;
- multi-user sessions excluded;
- sessions longer than 24 hours (kept) and the sensitivity of headline rates to them;
- unknown category share and unknown brand share, of events and of revenue;
- category codes mapping to multiple ids;
- carted pairs whose cart events are all zero-price (counted in pair counts, excluded from value).

## Changes

### 2026-09-26 · Clarifications before the first mart build (Sections 6, 9, 10)

**Reason:** while building the dbt pipeline (Sprint 1 Step 3), Claude Code found one contradiction and two gaps in the text committed in `8d4093f`. The project owner decided each one. No business metric had been computed or published when this entry was made.

1. **Section 10, basis for session exclusions.** Null-session events excluded and multi-user sessions excluded are counted on deduplicated events *before* session exclusions. By definition they are not part of any valid session, so the "deduplicated events in valid sessions" basis cannot apply to them. All other data-quality metrics except exact duplicate rows removed (raw rows) stay on deduplicated events in valid sessions.
2. **Section 9, what the category funnel publishes.** Per top-level category, and per full `category_code` in drill-downs, it publishes:
   - step counts: (session, category) pairs with a view in the category, those with a cart event in the category, and those with a purchase in the category;
   - within-category step rates: view-to-cart (pairs with a cart event in the category ÷ pairs entering the funnel) and cart-to-purchase (pairs with a cart event and a purchase in the category ÷ pairs with a cart event in the category);
   - category revenue: the sum of purchase price over all purchase events in the category, in valid sessions, whether or not the session entered that category's funnel. Category revenues therefore sum to total revenue.

   The cart-to-purchase numerator requires both a cart event and a purchase in the category, so the rate cannot exceed 100% even though most purchases have no same-session cart event (Section 5).

   Every category view states the unknown share of events and of revenue. It also discloses that one session can appear in several category funnels, so category counts do not sum to session totals. Carted value with no observed purchase in this session (Section 7) is grouped by the top-level category on the pair's latest cart event, and by the full code on that event in drill-downs.
3. **Section 6, cart-session purchase rate.** "A purchase of a product carted in that session" means a purchase of a product that has a cart event anywhere in the same session, consistent with Section 5. There is no timing condition.

**Effect on published numbers:** none; no numbers had been published. Items 1 and 3 fix how metrics already listed are computed. Item 2 defines the category funnel's published fields.

### 2026-09-26 · Category cart-to-purchase rate and category revenue population (Section 9)

**Reason:** the project owner tightened item 2 of the previous entry so the category rate mirrors the Section 6 cart-session purchase rate exactly. That decision came after the previous entry was committed, so it is recorded here rather than by editing that entry.

1. **Within-category cart-to-purchase rate** (supersedes the numerator in the previous entry, item 2):
   - numerator: (session, top-level category) pairs with at least one purchase of a product in that category that has a cart event anywhere in the same session;
   - denominator: (session, top-level category) pairs with at least one cart event in the category.

   The same definition applies per full `category_code` in drill-downs. The rate is always at most 100%.
2. **Category revenue population.** Category revenue covers all purchase events in the category in valid sessions, so category revenues sum to total revenue; a reconciliation test asserts this. This population differs slightly from the category funnel's, which contains only (session, category) pairs entered by a view in the category. The funnel page discloses this difference alongside the carted-value population note (Section 7).

**Effect on published numbers:** none; no numbers had been published.

### 2026-09-26 · Session-level purchase paths and cart sessions with a purchase of no carted product (Sections 5, 6)

**Reason:** the funnel page's purchase step reads as a widening funnel, because most purchases have no observed same-session cart event (Section 5). Showing that step split by path, and completing the cart-session breakdown, needs two session-level counts the contract did not define. The project owner approved this entry before either count was computed.

1. **Section 5, session level.** A valid session with an observed purchase is classified by its purchase events:
   - "Sessions with an observed purchase of a product with an observed same-session cart event" (legend label: "Purchase of a carted product"): at least one of its purchase events is on the path "Purchase with an observed same-session cart event". This equals the numerator of "Sessions with an observed cart event and an observed purchase of a carted product (%)" (Section 6).
   - "Sessions with observed purchases only of products with no observed same-session cart event" (legend label: "Purchases only of products not carted in the session"): every one of its purchase events is on the path "Purchase with no observed same-session cart event".

   The two sum to sessions with an observed purchase. Chart legends use the legend labels; tables and tooltips use the full labels.
2. **Section 6, cart sessions with a purchase of no carted product.**
   - "Sessions with an observed cart event and an observed purchase, none of a carted product" (display label): valid sessions with at least one cart event and at least one purchase event, none of them of a product carted in that session. With the numerator of "Sessions with an observed cart event and an observed purchase of a carted product (%)" and "Sessions with an observed cart event and no observed purchase in this session", it partitions sessions with an observed cart event; a reconciliation test asserts the three sum to sessions with an observed cart event.

**Effect on published numbers:** no published number changes. Three counts are added to the funnel page: the two session-level purchase groups and the cart sessions with a purchase of no carted product.
