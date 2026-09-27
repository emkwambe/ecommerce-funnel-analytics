-- metrics.md Changes 2026-09-26 (Sprint 3 ranking), items 1-4, 10, 11, and 12: one row per (level, valid session,
-- category) entered by at least one view in the category (the Section 9 category funnel population), at the
-- top level and at the full-code drill-down. "unknown" rows are kept here so the reconciliation test can count
-- them (item 5); funnel.rankings excludes them from every ranking (item 3).
--   has_purchase           at least one purchase event of a product in the category (item 4)
--   revenue                price over purchase events of products in the category, zero-price excluded (item 11)
--   revenue_collapsed      over distinct (session, product) purchase pairs whose earliest purchase event is in the
--                          category: the price on that event (Section 4; item 11)
--   is_long_session        session longer than 24 hours (item 12, sensitivity C6)
--   is_most_active_user    user above the 99.9th percentile of deduplicated events in valid sessions (C7; the
--                          Sprint 2 B7 rule)
--   has_missing_code_event the session has an event of a product with a missing code (C8)
-- Not exported to the site: funnel.rankings reads it for the user-clustered bootstrap.
{% set levels = [('category_top', 'category_top'), ('category_code', 'category_code_label')] %}

with valid_events as (
    select
        e.user_session, e.product_id, e.event_type, e.event_time, e.price_amount, e.is_zero_price,
        e.category_top, e.category_code_label, s.user_id, s.is_long_session
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

session_flags as (
    select user_session, bool_or(category_code_label = 'unknown') as has_missing_code_event
    from valid_events
    group by user_session
),

user_events as (
    select user_id, count(*) as events from valid_events group by user_id
),

active_threshold as (
    select quantile_disc(events, 0.999) as threshold_events from user_events
),

most_active_users as (
    select u.user_id from user_events as u cross join active_threshold as t where u.events > t.threshold_events
),

-- Section 4: the earliest purchase event of each (session, product) pair. assert_purchase_pair_single_category
-- requires one category per pair at each level, so taking it from the earliest event changes nothing.
purchase_pairs as (
    select
        user_session,
        product_id,
        arg_min(price_amount, event_time) as earliest_price,
        arg_min(category_top, event_time) as category_top,
        arg_min(category_code_label, event_time) as category_code_label
    from valid_events
    where event_type = 'purchase' and not is_zero_price
    group by user_session, product_id
)

{% for level, col in levels %}
,

pairs_{{ level }} as (
    select
        user_session,
        {{ col }} as category,
        any_value(user_id) as user_id,
        any_value(is_long_session) as is_long_session,
        bool_or(event_type = 'view') as has_view,
        bool_or(event_type = 'purchase') as has_purchase,
        coalesce(sum(price_amount) filter (where event_type = 'purchase' and not is_zero_price), 0) as revenue
    from valid_events
    group by user_session, {{ col }}
),

collapsed_{{ level }} as (
    select user_session, {{ col }} as category, sum(earliest_price) as revenue_collapsed
    from purchase_pairs
    group by user_session, {{ col }}
),

level_{{ level }} as (
    select
        '{{ level }}' as category_level,
        p.category,
        p.user_session,
        p.user_id,
        p.has_purchase,
        p.revenue,
        coalesce(c.revenue_collapsed, 0) as revenue_collapsed,
        p.is_long_session,
        p.user_id in (select user_id from most_active_users) as is_most_active_user,
        f.has_missing_code_event
    from pairs_{{ level }} as p
    left join collapsed_{{ level }} as c using (user_session, category)
    inner join session_flags as f using (user_session)
    where p.has_view
)
{% endfor %}

{% for level, _ in levels %}
select * from level_{{ level }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
