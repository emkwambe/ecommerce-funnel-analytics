-- metrics.md Changes 2026-09-26 (second entry), item 1: the within-category cart-to-purchase rate
-- is always at most 100%. Returns categories where a funnel pair has a purchase of a carted product
-- in the category but no cart event in the category (it would sit outside the denominator), or where
-- either step rate exceeds 1. Any row fails the build.
select category_key, funnel_pairs_with_carted_product_purchase_but_no_category_cart,
       view_to_cart_step_rate, cart_to_purchase_step_rate
from {{ ref('mart_funnel_category') }}
where funnel_pairs_with_carted_product_purchase_but_no_category_cart > 0
   or view_to_cart_step_rate > 1
   or cart_to_purchase_step_rate > 1
