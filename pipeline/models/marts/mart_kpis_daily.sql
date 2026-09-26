-- metrics.md Sections 4 and 6 by UTC day of session start (Section 9, Time), plus the month total.
-- Each session, its order, and its revenue count on the UTC day of the session's first event.
with pair_rollup as (
    select
        user_session,
        -- Section 6, cart-session purchase rate: a purchase of a product carted in that session.
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
),

session_facts as (
    select
        s.session_start_day_utc,
        s.has_view,
        s.has_cart,
        s.has_purchase,
        coalesce(p.has_purchase_of_carted_product, false) as has_purchase_of_carted_product,
        coalesce(r.revenue, 0) as revenue,
        coalesce(p.revenue_repeat_collapsed, 0) as revenue_repeat_collapsed
    from {{ ref('int_sessions') }} as s
    left join pair_rollup as p using (user_session)
    left join session_revenue as r using (user_session)
),

periods as (
    select 'day' as period_type, session_start_day_utc as period_start, * exclude (session_start_day_utc)
    from session_facts
    union all
    select 'month' as period_type, cast(date_trunc('month', session_start_day_utc) as date) as period_start,
           * exclude (session_start_day_utc)
    from session_facts
),

counts as (
    select
        period_type,
        period_start,
        count(*) as sessions,
        count(*) filter (where has_view) as sessions_with_view,
        count(*) filter (where has_cart) as sessions_with_cart,
        count(*) filter (where has_purchase) as sessions_with_purchase,
        count(*) filter (where has_purchase) as orders,
        count(*) filter (where has_view and has_cart) as viewing_sessions_with_cart,
        count(*) filter (where has_cart and has_purchase_of_carted_product) as cart_sessions_with_carted_product_purchase,
        count(*) filter (where has_cart and not has_purchase) as cart_sessions_with_no_observed_purchase,
        sum(revenue) as revenue,
        sum(revenue_repeat_collapsed) as revenue_repeat_collapsed
    from periods
    group by period_type, period_start
)

select
    period_type || ':' || cast(period_start as varchar) as period_key,
    period_type,
    period_start,
    case when period_type = 'day' then 'UTC day of session start' else 'Month, UTC day of session start' end
        as period_label,
    sessions,
    sessions_with_view,
    sessions_with_cart,
    sessions_with_purchase,
    orders,
    viewing_sessions_with_cart,
    cart_sessions_with_carted_product_purchase,
    cart_sessions_with_no_observed_purchase,
    revenue,
    revenue_repeat_collapsed,
    sessions_with_purchase / nullif(sessions, 0) as session_purchase_rate,
    viewing_sessions_with_cart / nullif(sessions_with_view, 0) as view_to_cart_session_rate,
    cart_sessions_with_carted_product_purchase / nullif(sessions_with_cart, 0) as cart_session_purchase_rate,
    revenue / nullif(orders, 0) as average_order_value,
    revenue / nullif(sessions, 0) as revenue_per_session
from counts
