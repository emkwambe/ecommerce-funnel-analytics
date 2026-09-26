-- One row per valid session (metrics.md Section 3): user_session as logged, excluding
-- events with a null user_session and sessions containing more than one user_id.
-- More than one user_id is detected as min(user_id) <> max(user_id), as in funnel.profile.
with session_rollup as (
    select
        user_session,
        min(user_id) as user_id,
        min(user_id) <> max(user_id) as has_multiple_user_ids,
        min(event_time) as session_start,
        max(event_time) as session_end,
        count(*) as event_count,
        count(*) filter (where event_type = 'view') as view_event_count,
        count(*) filter (where event_type = 'cart') as cart_event_count,
        count(*) filter (where event_type = 'purchase') as purchase_event_count
    from {{ ref('stg_events') }}
    where user_session is not null
    group by user_session
)

select
    user_session,
    user_id,
    session_start,
    session_end,
    cast(session_start as date) as session_start_day_utc,
    view_event_count > 0 as has_view,
    cart_event_count > 0 as has_cart,
    purchase_event_count > 0 as has_purchase,
    session_end - session_start > interval 24 hour as is_long_session,
    event_count,
    view_event_count,
    cart_event_count,
    purchase_event_count
from session_rollup
where not coalesce(has_multiple_user_ids, false)
