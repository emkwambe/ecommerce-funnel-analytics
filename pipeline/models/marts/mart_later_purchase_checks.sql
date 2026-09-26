-- Changes 2026-09-26 (Sprint 2 investigations), B items 14-16: the most-active-user threshold, the user_id checks
-- (item 15, published as data quality), and the diagnostics (item 16, published beside the estimate, not as
-- findings). "Eligible" means the B1 population (carted, 7 days).
with b1 as (
    select * from {{ ref('int_later_purchase_spec_pairs') }} where spec_key = 'B1'
),

b1_sessions as (
    select distinct user_session from b1
),

eligible_session_events as (
    select e.user_session, e.user_id
    from {{ ref('stg_events') }} as e
    inner join b1_sessions using (user_session)
),

user_events as (
    select s.user_id, count(*) as events
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
    group by s.user_id
),

sessions_per_user as (
    select user_id, count(*) as sessions from {{ ref('int_sessions') }} group by user_id
),

users_by_eligible_pairs as (
    select
        user_id,
        count(*) as eligible_pairs,
        count(*) filter (where is_followed) as followed_pairs,
        row_number() over (order by count(*) desc, user_id) as rank_by_eligible_pairs,
        count(*) over () as users
    from b1
    group by user_id
),

metrics as (
    select 'user_id_check' as metric_group, 'events_in_eligible_sessions_with_null_user_id' as metric_key,
           cast(count(*) filter (where user_id is null) as double) as value, 1 as sort_order
    from eligible_session_events
    union all
    select 'user_id_check', 'eligible_sessions_with_more_than_one_user_id',
           cast(count(*) as double), 2
    from (select user_session from eligible_session_events group by user_session having count(distinct user_id) > 1)
    union all
    select 'user_id_check', 'share_of_eligible_pairs_with_non_null_user_id',
           cast(count(user_id) as double) / count(*), 3
    from b1
    union all
    select 'sensitivity_threshold', 'most_active_user_threshold_events',
           cast(quantile_disc(events, 0.999) as double), 10
    from user_events
    union all
    select 'sensitivity_threshold', 'most_active_users_excluded',
           cast(count(*) filter (where events > (select quantile_disc(events, 0.999) from user_events)) as double), 11
    from user_events
    union all
    select 'diagnostic', 'eligible_pairs_followed', cast(count(*) filter (where is_followed) as double), 20
    from b1
    union all
    select 'diagnostic', 'eligible_pairs_followed_without_session_start_condition',
           cast(count(*) filter (
               where coalesce(first_purchase_time_any_session_start < session_start + interval 7 day, false)
           ) as double), 21
    from b1
    union all
    select 'diagnostic', 'share_of_followed_pairs_with_first_later_purchase_within_1_hour_of_latest_cart_event',
           cast(count(*) filter (where first_later_purchase_time - anchor_time <= interval 1 hour) as double)
               / nullif(count(*), 0), 22
    from b1 where is_followed
    union all
    select 'diagnostic', 'share_of_followed_pairs_held_by_top_0_1_pct_users_by_eligible_pairs',
           cast(sum(followed_pairs) filter (where rank_by_eligible_pairs <= ceil(users * 0.001)) as double)
               / nullif(sum(followed_pairs), 0), 23
    from users_by_eligible_pairs
    union all
    select 'diagnostic', 'top_0_1_pct_users_by_eligible_pairs', cast(max(ceil(users * 0.001)) as double), 24
    from users_by_eligible_pairs
    {% for q in [0.5, 0.9, 0.99, 1.0] %}
    union all
    select 'diagnostic', 'valid_sessions_per_user_p{{ (q * 100) | int }}',
           cast(quantile_disc(sessions, {{ q }}) as double), {{ 30 + loop.index }}
    from sessions_per_user
    {% endfor %}
)

select metric_group || ':' || metric_key as row_key, * from metrics
