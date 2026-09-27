# Closing Content — E-commerce Funnel Analytics

**Status:** owner-approved content for the closing report, the `/questions` export and page, and the home page (see the owner decision that accompanies this file).

**Number binding rule:** every figure below must be rendered from its named export field at build time. If a figure here differs from the export, **the export wins**. The build fails and the difference is reported. Figures in this file are never typed into a page.

## Four headline findings (home page)

| # | Finding (as published) | Tier | Bound to |
|---|---|---|---|
| F1 | In October 2019, 48% of revenue came from purchases with no observed same-session cart event. A funnel that assumes view → cart → purchase describes only about half of the business. | shows | `purchase_paths.json` revenue share, no-cart path |
| F2 | For carted products in sessions starting October 1–24, 2019 (UTC), 13.4% of the carted value with no observed purchase in the session was followed by a purchase of the same product by the same user within 7 days. Carted value with no purchase in the session is not the same as value never purchased. | shows | the analysis-B export's value share, with its population label |
| F3 | The two revenue figures differ by $18.5M, entirely because of repeated purchase events of the same product within a session. The data cannot tell whether these are extra units or the same purchase logged again. | shows | analysis-A export: the gap and its decomposition |
| F4 | A pre-registered category ranking was not published. On synthetic data where every category had the same rate, its rule still reported differences, so it could not be trusted to separate real ones. | shows (a method result) | the escalation brief and the synthetic-null evidence |

## Nine questions worth asking next

Groups (who can answer):
- **Product and engineering:** questions 1, 2 and 3.
- **More data:** questions 4, 5 and 9.
- **Better methods:** questions 6 and 7.
- **Only an experiment:** question 8.

**Question 1 is the project's answer to "what should the team test first?"** Before testing any change to the funnel, find out how the half of purchases that bypass the cart actually happen. The answer decides where every later test should aim.

| # | Question | Card line | Why it matters (full) | Who can answer | Evidence link |
|---|---|---|---|---|---|
| 1 | How do purchases with no observed same-session cart event happen? A "buy now" option, an app flow, or a logging behavior? | 48% of revenue takes this path | Nearly half of revenue bypasses the cart, so any effort aimed at the cart addresses at most half the business. Knowing the mechanism decides where tests should aim. | Product and engineering: checkout flows and tracking design | `/funnel` (purchase paths section) |
| 2 | Are repeated purchase events of the same product in a session extra units or the same purchase logged again? | Decides the $18.5M revenue gap | The two revenue figures differ by $18.5M because of these events. Until this is known, every revenue figure must be shown both ways. | Engineering: the order system and event schema | `/investigations/revenue-figures` |
| 3 | Does one `user_id` mean one person across sessions and devices? | Cross-session findings depend on it | Every finding that links sessions, including later purchases, assumes the identity holds. The checks available in the data passed, but cross-device identity can't be verified from this file. | The identity and tracking owners | `/investigations/later-purchases` (identity checks) |
| 4 | What happens to carted items beyond 7 days, and beyond October? | 13.4% is a one-month lower bound | The later-purchase share was measured within 7 days, inside one month. Purchases later, or outside the data's window, aren't observed. | More months of data | `/investigations/later-purchases` |
| 5 | Why did products carted in late October show a lower later-purchase rate? | Calendar, promotions, or data end | The late-October group differed from the early-October group, and the reason isn't in the data. It limits how far the 7-day figure generalizes. | A promotions calendar, plus more months of data | `/investigations/later-purchases` (late-October finding) |
| 6 | Which categories truly differ in conversion, and what rule can say so reliably? | The ranking rule failed its null test | The pre-registered ranking rule reported differences even when none existed. A rule must first pass a test on synthetic data with a known answer. | Better methods: a rule calibrated on synthetic data with a known answer | The escalation brief on GitHub (link to the committed file) |
| 7 | How much does automated or bot traffic shape the numbers? | Needs a pre-registered check | Heavy automated users could distort rates. This must be checked with a pre-registered, labeled sensitivity analysis, never an exclusion made after seeing results. | Better methods: a pre-registered sensitivity analysis | `/data-quality` |
| 8 | Would changing a step in the funnel actually change revenue? | Everything so far is descriptive | Every finding here describes what happened. None shows what a change would cause. | Only an experiment | `/funnel` |
| 9 | What is the profit picture, not just revenue? | Revenue is not margin | The data has no margins or returns, so a revenue-heavy category isn't necessarily a profitable one. | More data: margin and returns | `/data` (limitations) |
