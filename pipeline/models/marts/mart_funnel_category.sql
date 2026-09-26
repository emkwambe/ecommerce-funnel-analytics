-- metrics.md Section 9 category funnel (with Changes 2026-09-26) and Section 7 carted value,
-- one row per category at two levels: top-level category (headline) and full code (drill-down).
--
-- Funnel population: (valid session, category) pairs with at least one view in the category.
-- Cart and purchase steps count only events in that category within the session. One session
-- can enter several category funnels, so counts do not sum to session totals.
-- Category revenue and events cover all events in the category in valid sessions (not only
-- funnel pairs), so they sum to the totals. Carted value is grouped by the category on each
-- pair's latest cart event, with no view requirement (Section 7).
{% set levels = [
    ('category_top', 'category_top', 'latest_cart_category_top'),
    ('category_code', 'category_code_label', 'latest_cart_category_code_label'),
] %}

with valid_events as (
    select e.user_session, e.product_id, e.event_type, e.category_top, e.category_code_label
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

carted_products as (
    select user_session, product_id
    from {{ ref('int_session_products') }}
    where is_carted
)

{% for level, event_col, cart_col in levels %}
,

pairs_{{ level }} as (
    select
        {{ event_col }} as category,
        user_session,
        bool_or(event_type = 'view') as has_view,
        bool_or(event_type = 'cart') as has_cart,
        bool_or(event_type = 'purchase') as has_purchase
    from valid_events
    group by {{ event_col }}, user_session
),

-- Changes 2026-09-26 (second entry), item 1: a purchase of a product in the category that has
-- a cart event anywhere in the same session.
carted_product_purchase_pairs_{{ level }} as (
    select distinct e.{{ event_col }} as category, e.user_session
    from valid_events as e
    inner join carted_products as c using (user_session, product_id)
    where e.event_type = 'purchase'
),

funnel_{{ level }} as (
    select
        p.category,
        count(*) filter (where p.has_view) as funnel_pairs,
        count(*) filter (where p.has_view and p.has_cart) as funnel_pairs_with_cart,
        count(*) filter (where p.has_view and p.has_purchase) as funnel_pairs_with_purchase,
        count(*) filter (where p.has_view and p.has_cart and cp.user_session is not null)
            as funnel_cart_pairs_with_carted_product_purchase,
        -- Numerator pairs outside the cart step would break "always at most 100%";
        -- assert_category_cart_to_purchase_within_cart_step requires this to be zero.
        count(*) filter (where p.has_view and not p.has_cart and cp.user_session is not null)
            as funnel_pairs_with_carted_product_purchase_but_no_category_cart
    from pairs_{{ level }} as p
    left join carted_product_purchase_pairs_{{ level }} as cp using (category, user_session)
    group by p.category
),

events_{{ level }} as (
    select {{ event_col }} as category, count(*) as events
    from valid_events
    group by {{ event_col }}
),

revenue_{{ level }} as (
    select {{ event_col }} as category, count(*) as purchase_events, sum(price) as revenue
    from {{ ref('int_purchases') }}
    group by {{ event_col }}
),

carted_{{ level }} as (
    select
        {{ cart_col }} as category,
        count(*) as carted_pairs,
        count(*) filter (where is_purchased) as carted_pairs_with_purchase,
        count(*) filter (where not is_purchased) as carted_pairs_with_no_observed_purchase,
        count(*) filter (where is_zero_price_carted_pair) as zero_price_carted_pairs,
        coalesce(sum(latest_nonzero_cart_price) filter (where not is_purchased), 0)
            as carted_value_with_no_observed_purchase
    from {{ ref('int_session_products') }}
    where is_carted
    group by {{ cart_col }}
),

level_{{ level }} as (
    select
        '{{ level }}' as category_level,
        ev.category,
        ev.events,
        coalesce(f.funnel_pairs, 0) as funnel_pairs,
        coalesce(f.funnel_pairs_with_cart, 0) as funnel_pairs_with_cart,
        coalesce(f.funnel_pairs_with_purchase, 0) as funnel_pairs_with_purchase,
        coalesce(f.funnel_cart_pairs_with_carted_product_purchase, 0)
            as funnel_cart_pairs_with_carted_product_purchase,
        coalesce(f.funnel_pairs_with_carted_product_purchase_but_no_category_cart, 0)
            as funnel_pairs_with_carted_product_purchase_but_no_category_cart,
        coalesce(r.purchase_events, 0) as purchase_events,
        coalesce(r.revenue, 0) as revenue,
        coalesce(c.carted_pairs, 0) as carted_pairs,
        coalesce(c.carted_pairs_with_purchase, 0) as carted_pairs_with_purchase,
        coalesce(c.carted_pairs_with_no_observed_purchase, 0) as carted_pairs_with_no_observed_purchase,
        coalesce(c.zero_price_carted_pairs, 0) as zero_price_carted_pairs,
        coalesce(c.carted_value_with_no_observed_purchase, 0) as carted_value_with_no_observed_purchase
    from events_{{ level }} as ev
    left join funnel_{{ level }} as f using (category)
    left join revenue_{{ level }} as r using (category)
    left join carted_{{ level }} as c using (category)
)
{% endfor %}

, unioned as (
    {% for level, _, _ in levels %}
    select * from level_{{ level }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    category_level || ':' || category as category_key,
    *,
    funnel_pairs_with_cart / nullif(funnel_pairs, 0) as view_to_cart_step_rate,
    funnel_cart_pairs_with_carted_product_purchase / nullif(funnel_pairs_with_cart, 0) as cart_to_purchase_step_rate
from unioned
