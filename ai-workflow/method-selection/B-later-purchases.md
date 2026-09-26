# Method Selection — B. Were carted products purchased in a later session?

Template: verified-analytics-project v2.1 (`assets/templates/method-selection.md`). Written in Sprint 2 Step 2 (2026-09-26), before any Sprint 2 quantity is computed. No outcome in this record comes from a new query: the structural facts cited are from the committed Sprint 0 profile and `docs/data-source.md`. **Status: draft for the owner's decision (H2).** Epistemic risk: **consequential** (the sprint brief). R2, R3, a comparison control, adversarial review, and H9 sign-off apply.

**Question:** "Of carted value with no observed purchase in the session, how much did the same user purchase in a later session?"

**Question type:** descriptive and longitudinal. **Not causal.**

**Decision supported:** whether "carted value with no observed purchase in the session" (published in Sprint 1) should be read as value never purchased. It qualifies how Sprint 3 may frame what to test. It supports no estimate of value that could be recovered.

**Estimand (primary):** among **eligible carted pairs**, the share followed by a purchase of the same `product_id` by the same `user_id` in a **later session** within **7 days** of the cart session's start. It is reported two ways:

- **count share:** followed eligible pairs ÷ eligible pairs;
- **value share:** carted value of followed eligible pairs ÷ carted value of eligible pairs.

Definitions:

- **Eligible carted pair:** a (session, product) pair in a valid session (`docs/metrics.md` §3) with at least one cart event and no purchase event of that product in the session. This is the population of "carted value with no observed purchase in this session" (§7). The session must also start at or before the window's cutoff: 7 days → **2019-10-24 23:59:59 UTC**.
- **Window:** a purchase event time t with session start ≤ t < session start + N days. With the cutoff, every eligible pair has its full window inside the data (the last event is at 2019-10-31 23:59:59 UTC, `docs/data-source.md`).
- **Later session:** see decision B-D1. Recommended: a different valid session of the same `user_id` that **starts after** the cart session starts.
- **Carted value:** the pair's latest non-zero cart price (§7). Pairs whose cart events are all zero-price count in the count share and are excluded from the value share (§7 practice).
- **Population period:** cart sessions starting 2019-10-01 00:00:00 to the cutoff, UTC.

**Claim ceiling:** "N% of this carted value (M% of carted products) was followed by a purchase of the same product by the same user in a later session within 7 days." This **cannot** support "the cart caused the purchase", "was recovered", any statement about loss, or any statement about users' purchases outside this log (other devices, other accounts, other stores, after October 2019).

## Data-generating process (relevant features)

- **Identity.** `user_id` has no nulls (`docs/data-profile.md`), and sessions with more than one `user_id` are excluded (§3). What `user_id` represents (a logged-in account, a device, or a cookie) is not documented. If it is device- or cookie-bound, purchases on another device are invisible and the share is understated. If it is ever reused across people, the share is overstated. Uncertainty register U2.
- **One month of data, so right-censoring.** A pair carted on 30 October has one day of observable follow-up. A naive share over all pairs is biased downward for late-month pairs. The cutoff removes this for the fixed-window estimate; the Kaplan–Meier estimate models it instead.
- **Left-truncation.** A cart in early October may be a return to a product carted in September; that history is invisible. It does not bias the forward-looking estimand, but "first cart" cannot be claimed.
- **Clustering.** One user can have many eligible pairs, and one later purchase can "follow" several pairs (the same product carted in several sessions). Pairs are not independent, so uncertainty is estimated over users.
- **Sessions are as logged.** How the platform starts a new `user_session` (inactivity, app restart, login) is unknown. A "later session" may be a technical split of one visit. Diagnostic: the distribution of time from cart session start to the later purchase, with the share inside one hour reported.
- **Calendar effects.** Purchase propensity may vary through the month (paydays, promotions). The fixed-window population (sessions to 24 October) and the Kaplan–Meier population (all of October) differ in calendar mix.
- **Heavy or automated users.** A small number of users with extreme activity can dominate pair counts.

## Candidate methods

| Method | Assumptions | Verifiable how? | Fits this data-generating process? | Verdict |
|---|---|---|---|---|
| (1) Fixed-window share with a censoring-safe cutoff (7 days; sensitivity at 3 and 14 days with their own cutoffs: 2019-10-28 and 2019-10-17 23:59:59 UTC) | Full follow-up for every included pair (guaranteed by the cutoff); `user_id` links a person across sessions | Cutoff: by construction, with a test that the latest included session start plus N days is within the data. Identity: partially (the `user_id` checks below); otherwise untestable, handled as a stated limitation | Yes | **chosen (primary)** |
| (2) Kaplan–Meier estimate of time from cart session start to the first later-session purchase of the product, all eligible pairs (no cutoff), censored at 2019-10-31 23:59:59 UTC | Censoring is non-informative (here administrative: end of data), so it holds if the purchase hazard does not depend on the calendar date | The fixed-window estimate (1) comparing with KM at 7 days is itself the check; KM 1−S(t) is also reported at 3 and 14 days | Yes, with the calendar caveat | **chosen (R3)** |
| (3) Naive share over all eligible pairs, no cutoff | Equal follow-up for all pairs | False by construction: follow-up ranges from 31 days to 0 | No | **rejected**: biased downward by right-censoring |
| (4) Regression (logistic or Cox) of later purchase on price, category, and so on | A model of covariate effects | — | Answers a different question (associations with covariates), invites causal reading | **rejected**: no covariate question in scope; category and price breakdowns are Sprint 3 decisions and need Changes entries |
| (5) User-level grain: (user, product) first eligible pair only | Removes double-following when one product is carted in several sessions | By comparison with (1) | Yes | **pre-specified sensitivity**, not primary: the Sprint 1 metric is at pair grain, so the primary estimand stays at pair grain |

**Uncertainty:** a user-clustered bootstrap (resample users with replacement, keeping all their pairs), 2,000 resamples, a fixed seed recorded in the output, and 95% percentile intervals. It applies to the count and value shares and to the KM curve. Greenwood intervals for KM are **rejected** because they assume independent pairs.

**Comparison control (the brief's negative control):** for the same eligible sessions (sessions containing at least one eligible carted pair), (session, product) pairs with at least one view, no cart event, and no purchase of the product in the session. The same window, cutoff, later-session rule, and bootstrap apply, with the pair's latest non-zero view price as value. It separates a cart-specific pattern from general return-and-buy behavior. **It is a comparison baseline, not a pure negative control**: view-only products can also be bought later for real reasons, so it is not expected to be zero. The expectation, fixed now: if the carted-pair share is **not** above the view-only share, the cart-specific reading is not supported and the step stops for escalation.

## `user_id` reliability checks (before any estimate is viewed)

1. Missing `user_id` among events in eligible sessions (the profile shows 0 on all rows; confirmed on the population).
2. Sessions spanning more than one `user_id` (excluded by §3; confirmed as 0 in the population).
3. The share of eligible pairs with a usable `user_id` (expected 100% given 1 and 2; reported).
4. Diagnostics, reported, not gates: users' sessions in the month (distribution); overlapping sessions of the same user (a session that starts before the cart session ends), which shows how much B-D1 matters; the time from cart session start to the later purchase (share within one hour).

## Failure conditions

- **R2 mismatch** (any cell): stop; a bug in one path.
- **R3 disagreement:** the fixed-window 7-day count share lies outside the KM 7-day 95% interval. Stop and escalate before interpreting. Candidates: calendar effects (the populations differ), the censoring assumption, or a bug.
- **Comparison control not below the main estimate:** stop and escalate (above).
- **Identity failure:** checks 1–2 non-zero, or check 3 below 100%. Stop and escalate.
- **Dominance:** the top 0.1% of users by eligible pairs hold more than 10% of followed pairs. Report it, and let the bot-like-user sensitivity decide the wording.
- **Surprise** (the brief's slow-down trigger): any of the above, or a share that the owner finds implausible on review. The step stops with an escalation brief before any interpretive sentence is written.

## Robustness plan (all pre-specified; every run logged in `ai-workflow/search-log.md`)

| # | Specification | Role |
|---|---|---|
| B1 | 7-day window, cutoff 2019-10-24, pair grain, count and value shares with bootstrap intervals | primary |
| B2 | 3-day window, cutoff 2019-10-28 | sensitivity |
| B3 | 14-day window, cutoff 2019-10-17 | sensitivity |
| B4 | KM (count), all eligible pairs, 1−S at 3, 7, and 14 days, bootstrap band; value-weighted KM as secondary | R3 |
| B5 | Comparison control (view-only pairs), 7-day, same cutoff | control |
| B6 | (user, product) grain, first eligible pair per user and product | sensitivity (multiple carts of the same product) |
| B7 | Excluding users above the 99.9th percentile of events in the month (the threshold is computed on the structural event count, before any outcome) | sensitivity (bot-like users) |
| B8 | Excluding cart sessions longer than 24 hours | sensitivity (consistent with §3 practice) |
| B9 | `user_id` checks 1–4 | data check |
| R2 | `funnel.verify` recomputes B1 (count and value shares) independently of dbt | reproduction |

**Adversarial review (Step 5):** identity linking, censoring, bot-like users (B7), multiple carts of the same product (B6), technical session splits (diagnostic 4), and purchases by other people in the same household (unobservable; stated as a limitation).

## Decisions needed (H2)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| B-D1 | "Later session" | (a) a different valid session of the same user that **starts after** the cart session starts; (b) any other session of the user, with the purchase event after the cart session's **last** event; (c) a session that starts after the cart session **ends** | **(a)**: simple and unambiguous. Overlap is reported (diagnostic 4) so the effect of (c) is visible |
| B-D2 | Window and cutoffs | 7 days (cutoff 2019-10-24 23:59:59 UTC); sensitivities 3 days (2019-10-28) and 14 days (2019-10-17); window anchored at the cart session's start | **Approve as proposed** in the brief |
| B-D3 | Value basis | The pair's latest non-zero cart price (§7), zero-price pairs in counts only | **Approve** (consistent with the published figure it qualifies) |
| B-D4 | Comparison control | View-only pairs in the same eligible sessions (definition above), labeled "comparison baseline" | **Approve**, including the stop rule |
| B-D5 | Uncertainty | User-clustered bootstrap, 2,000 resamples, 95% percentile, fixed seed | **Approve** |
| B-D6 | R3 agreement rule | The fixed-window 7-day count share lies inside the KM 7-day 95% interval | **Approve** |
| B-D7 | Sensitivities B6, B7, and B8 | Include all three as pre-specified, or drop any | **Include all three** |
| B-D8 | Claim ceiling | As written above | **Approve** |
