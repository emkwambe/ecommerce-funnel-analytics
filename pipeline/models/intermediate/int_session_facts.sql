-- One row per valid session with the flags and values that Section 4 and Section 6 metrics
-- aggregate. Shared by mart_kpis_daily and the long-session sensitivity in mart_data_quality,
-- so both use one definition.
with pair_rollup as (
    select
        user_session,
        -- Section 6 (Changes 2026-09-26, item 3): a purchase of a product with a cart event
        -- anywhere in the same session.
        bool_or(is_carted and is_purchased) as has_purchase_of_carted_product,
        -- Section 4, secondary revenue: earliest purchase price per purchased pair.
        sum(earliest_purchase_price) filter (where is_purchased) as revenue_repeat_collapsed
    from {{ ref('int_session_products') }}
    group by user_session
),

session_revenue as (
    select user_session, sum(price) as revenue
    from {{ ref('int_purchases') }}
    group by user_session
)

select
    s.user_session,
    s.session_start_day_utc,
    s.is_long_session,
    s.has_view,
    s.has_cart,
    s.has_purchase,
    coalesce(p.has_purchase_of_carted_product, false) as has_purchase_of_carted_product,
    coalesce(r.revenue, 0) as revenue,
    coalesce(p.revenue_repeat_collapsed, 0) as revenue_repeat_collapsed
from {{ ref('int_sessions') }} as s
left join pair_rollup as p using (user_session)
left join session_revenue as r using (user_session)
