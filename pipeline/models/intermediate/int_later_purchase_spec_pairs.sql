-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), B items 7-11, 13, and 14: one row per (specification,
-- eligible pair), with whether the pair is followed within the specification's window (item 8, condition 4:
-- first later purchase time < session start + N days). The cutoffs are the entry's table (session start at or
-- before the cutoff). Specifications:
--   B1 carted, 7 days (primary)      B2 carted, 3 days           B3 carted, 14 days
--   B5 viewed (comparison baseline), 7 days, in sessions holding a B1 eligible pair
--   B6 carted, 7 days, one pair per (user, product): earliest cart-session start, ties by user_session
--   B7 carted, 7 days, excluding users above the 99.9th percentile of deduplicated events in valid sessions
--   B8 carted, 7 days, excluding cart sessions longer than 24 hours
{% set specs = [
    ('B1', 'carted', 7, '2019-10-24 23:59:59'),
    ('B2', 'carted', 3, '2019-10-28 23:59:59'),
    ('B3', 'carted', 14, '2019-10-17 23:59:59'),
    ('B5', 'viewed', 7, '2019-10-24 23:59:59'),
] %}
with pairs as (
    select * from {{ ref('int_later_purchase_pairs') }}
),

windowed as (
    {% for key, pair_type, days, cutoff in specs %}
    select
        '{{ key }}' as spec_key, {{ days }} as window_days, timestamp '{{ cutoff }}' as cutoff,
        p.*,
        coalesce(p.first_later_purchase_time < p.session_start + interval {{ days }} day, false) as is_followed
    from pairs as p
    where p.pair_type = '{{ pair_type }}' and p.session_start <= timestamp '{{ cutoff }}'
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

-- Item 13 (B5): sessions holding at least one B1 eligible pair. Viewed pairs exist only in
-- sessions with a carted pair (int_later_purchase_pairs), and B5 uses the same cutoff as B1, so this
-- restriction is already met; it is applied explicitly all the same.
b1_sessions as (
    select distinct user_session from windowed where spec_key = 'B1'
),

user_events as (
    select s.user_id, count(*) as events
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
    group by s.user_id
),

active_threshold as (
    select quantile_disc(events, 0.999) as threshold_events from user_events
),

most_active_users as (
    select u.user_id from user_events as u cross join active_threshold as t where u.events > t.threshold_events
)

select * from windowed where spec_key in ('B1', 'B2', 'B3')
union all
select w.* from windowed as w inner join b1_sessions using (user_session) where w.spec_key = 'B5'
union all
select * exclude (k) replace ('B6' as spec_key)
from (
    select *, row_number() over (partition by user_id, product_id order by session_start, user_session) as k
    from windowed where spec_key = 'B1'
) where k = 1
union all
select * replace ('B7' as spec_key)
from windowed where spec_key = 'B1' and user_id not in (select user_id from most_active_users)
union all
select * replace ('B8' as spec_key)
from windowed where spec_key = 'B1' and not is_long_session
