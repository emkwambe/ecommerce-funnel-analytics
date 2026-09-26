# Uncertainty Register — E-commerce Funnel Analytics

What we don't know yet. Material and critical items only. No sprint closes with an open **critical** item unless the human has accepted it in writing.

Template: trio-sprint-workflow v2.3. Created in Sprint 2 Step 0 (2026-09-26).

| ID | Date | Issue | Type (data / engineering / statistics / domain / product / security) | Impact (material / critical) | Current assumption | Evidence so far | Resolution path | Status |
|---|---|---|---|---|---|---|---|---|
| U1 | 2026-09-26 | Repeated purchase events of the same product in a session: extra units or repeated logging? This is the gap between the primary and the repeat-collapsed revenue. | data | material | Neither reading is assumed. Both revenue figures are always shown together (`docs/metrics.md` §4). | The file has no quantity column (column list in `docs/data-source.md`) and no order or transaction ID column (`docs/data-profile.md`: "Order or transaction ID columns: none found"). | Cannot be resolved from this file. Sprint 2 analysis A describes patterns *consistent with* each reading (timing, price, category, repeats per pair); its claim ceiling says which explanation is true cannot be established. | open (unresolvable from the data; bounded by the claim ceiling) |
| U2 | 2026-09-26 | Is `user_id` a reliable identity across sessions? Sprint 2 analysis B links a cart session to later purchases by the same `user_id`. | data | material | Not assumed. Within-session identity is checked (sessions with more than one `user_id` are excluded, `docs/metrics.md` §3); cross-session identity is untested. | Sprint 0 profile: multi-user sessions are excluded; missing `user_id` values not yet checked for B's population. | Sprint 2 Step 5 data check: missing values, sessions spanning users, share of eligible pairs with a usable `user_id`; adversarial review of identity linking. Cross-device and household purchases cannot be observed and remain a stated limitation. | open |

## Resolved
| ID | Resolution | How resolved (tool, evidence, human decision) | Date |
|---|---|---|---|
