-- Reconciliation (metrics.md Changes 2026-09-26, third entry, item 1): in every row, the two
-- session-level purchase groups sum to sessions with an observed purchase, and the group with a
-- purchase of a carted product equals the Section 6 cart-session purchase numerator.
select period_key, sessions_with_purchase, sessions_with_purchase_of_carted_product,
       sessions_with_purchases_only_of_uncarted_products, cart_sessions_with_carted_product_purchase
from {{ ref('mart_kpis_daily') }}
where sessions_with_purchase_of_carted_product + sessions_with_purchases_only_of_uncarted_products
          <> sessions_with_purchase
   or sessions_with_purchase_of_carted_product <> cart_sessions_with_carted_product_purchase
