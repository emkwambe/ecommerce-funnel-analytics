-- metrics.md Sections 4 and 6 by UTC day of session start (Section 9, Time), plus the month total.
-- Each session, its order, and its revenue count on the UTC day of the session's first event.
with session_facts as (
    select * exclude (user_session, is_long_session)
    from {{ ref('int_session_facts') }}
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
        -- Changes 2026-09-26 (third entry), item 1: session-level purchase paths.
        count(*) filter (where has_purchase and has_purchase_of_carted_product)
            as sessions_with_purchase_of_carted_product,
        count(*) filter (where has_purchase and not has_purchase_of_carted_product)
            as sessions_with_purchases_only_of_uncarted_products,
        -- Changes 2026-09-26 (third entry), item 2.
        count(*) filter (where has_cart and has_purchase and not has_purchase_of_carted_product)
            as cart_sessions_with_purchase_of_no_carted_product,
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
    sessions_with_purchase_of_carted_product,
    sessions_with_purchases_only_of_uncarted_products,
    cart_sessions_with_purchase_of_no_carted_product,
    revenue,
    revenue_repeat_collapsed,
    sessions_with_purchase / nullif(sessions, 0) as session_purchase_rate,
    viewing_sessions_with_cart / nullif(sessions_with_view, 0) as view_to_cart_session_rate,
    cart_sessions_with_carted_product_purchase / nullif(sessions_with_cart, 0) as cart_session_purchase_rate,
    revenue / nullif(orders, 0) as average_order_value,
    revenue / nullif(sessions, 0) as revenue_per_session
from counts
