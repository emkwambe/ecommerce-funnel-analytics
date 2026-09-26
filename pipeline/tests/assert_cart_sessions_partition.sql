-- Reconciliation (metrics.md Changes 2026-09-26, third entry, item 2): in every row, cart sessions
-- with a purchase of a carted product, with no observed purchase, and with a purchase of no carted
-- product sum to sessions with an observed cart event.
select period_key, sessions_with_cart, cart_sessions_with_carted_product_purchase,
       cart_sessions_with_no_observed_purchase, cart_sessions_with_purchase_of_no_carted_product
from {{ ref('mart_kpis_daily') }}
where cart_sessions_with_carted_product_purchase + cart_sessions_with_no_observed_purchase
      + cart_sessions_with_purchase_of_no_carted_product <> sessions_with_cart
