-- One row per deduplicated purchase event in a valid session (metrics.md Sections 4, 5).
-- Path: whether the purchased product has a cart event anywhere in the same session (D5).
select
    e.event_id,
    e.user_session,
    e.product_id,
    e.event_time,
    s.session_start_day_utc,
    e.price_amount as price,
    e.category_top,
    e.category_code_label,
    e.brand_label,
    case
        when sp.is_carted then 'Purchase with an observed same-session cart event'
        else 'Purchase with no observed same-session cart event'
    end as purchase_path
from {{ ref('stg_events') }} as e
inner join {{ ref('int_sessions') }} as s using (user_session)
inner join {{ ref('int_session_products') }} as sp using (user_session, product_id)
where e.event_type = 'purchase'
