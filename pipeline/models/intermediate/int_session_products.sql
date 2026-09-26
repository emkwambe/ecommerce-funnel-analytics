-- One row per (valid session, product) pair with at least one event (metrics.md Sections 4, 7).
-- Latest and earliest values are taken with arg_max / arg_min on event_time. Ties on the
-- deciding timestamp would make them ambiguous; the singular tests
-- assert_no_tied_latest_nonzero_cart_price, assert_no_tied_latest_cart_category and
-- assert_no_tied_earliest_purchase_price fail the build if any tie changes the value.
with valid_events as (
    select e.*
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
)

select
    user_session,
    product_id,
    count(*) filter (where event_type = 'view') > 0 as has_view,
    count(*) filter (where event_type = 'cart') > 0 as is_carted,
    count(*) filter (where event_type = 'purchase') > 0 as is_purchased,
    count(*) filter (where event_type = 'cart') as cart_event_count,
    count(*) filter (where event_type = 'purchase') as purchase_event_count,
    max(event_time) filter (where event_type = 'cart') as latest_cart_time,
    arg_max(price_amount, event_time) filter (where event_type = 'cart') as latest_cart_price,
    -- Section 7: carted value uses the price on the latest cart event whose price is above zero.
    arg_max(price_amount, event_time) filter (where event_type = 'cart' and price > 0) as latest_nonzero_cart_price,
    -- Section 7: carted pairs whose cart events are all zero-price stay in pair counts, not in value.
    count(*) filter (where event_type = 'cart') > 0
        and count(*) filter (where event_type = 'cart' and price > 0) = 0 as is_zero_price_carted_pair,
    -- Section 7: carted value is grouped by the category on the pair's latest cart event.
    arg_max(category_top, event_time) filter (where event_type = 'cart') as latest_cart_category_top,
    arg_max(category_code_label, event_time) filter (where event_type = 'cart') as latest_cart_category_code_label,
    -- Section 4 (secondary revenue): price on the earliest purchase event of the pair.
    arg_min(price_amount, event_time) filter (where event_type = 'purchase') as earliest_purchase_price
from valid_events
group by user_session, product_id
