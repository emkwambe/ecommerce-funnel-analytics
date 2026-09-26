-- metrics.md Section 10 (with Changes 2026-09-26, item 1): every data-quality metric with its
-- basis, and the Sprint 0 raw-basis figure alongside where Sprint 0 published one. The Sprint 0
-- figures are read from the committed profile.json, never typed.
-- Section 3: long-session sensitivity for the five headline metrics.
{% set profile_json = env_var('FUNNEL_REPO_ROOT', 'C:/Dev/ecommerce-funnel-analytics') ~ '/ai-workflow/evidence/sprint-0/profile.json' %}

with sprint0 as (
    select content as j from read_text('{{ profile_json }}')
),

s0 as (
    select
        cast(json_extract(j, '$.duplicates.exact_duplicate_rows.surplus_rows') as bigint) as duplicates,
        cast(json_extract(j, '$.price.zero_price_events') as bigint) as zero_price_events,
        cast(json_extract(j, '$.ordering_anomalies.cart_events_with_no_view_at_or_before_in_session') as bigint)
            as cart_no_view,
        cast(json_extract(j, '$.sessions_users.null_user_session_events') as bigint) as null_session_events,
        cast(json_extract(j, '$.sessions_users.sessions_with_more_than_one_user_id') as bigint) as multi_user_sessions,
        cast(json_extract(j, '$.sessions_users.sessions_spanning_more_than_24_hours') as bigint) as long_sessions,
        cast(json_extract(j, '$.category_brand.category_code.null_or_empty_count') as bigint) as unknown_category_events,
        cast(json_extract(j, '$.category_brand.brand.null_or_empty_count') as bigint) as unknown_brand_events,
        cast(json_extract(j, '$.category_brand.category_codes_mapping_to_more_than_one_category_id') as bigint)
            as multi_id_codes
    from sprint0
),

-- Basis: deduplicated events before session exclusions (Changes 2026-09-26, item 1).
dedup_before_exclusions as (
    select
        count(*) filter (where user_session is null) as null_session_events
    from {{ ref('stg_events') }}
),

multi_user as (
    select count(*) as multi_user_sessions
    from (
        select user_session
        from {{ ref('stg_events') }}
        where user_session is not null
        group by user_session
        having min(user_id) <> max(user_id)
    )
),

-- Basis: deduplicated events in valid sessions.
valid_events as (
    select e.*
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

valid_event_counts as (
    select
        count(*) as events,
        count(*) filter (where is_zero_price) as zero_price_events,
        count(*) filter (where category_top = 'unknown') as unknown_category_events,
        count(*) filter (where brand_label = 'unknown') as unknown_brand_events
    from valid_events
),

cart_no_view as (
    select count(*) as cart_events_with_no_view_at_or_before
    from valid_events as c
    where c.event_type = 'cart'
      and not exists (
          select 1 from valid_events as v
          where v.event_type = 'view'
            and v.user_session = c.user_session
            and v.product_id = c.product_id
            and v.event_time <= c.event_time
      )
),

multi_id_codes as (
    select count(*) as codes
    from (
        select category_code_label
        from valid_events
        where category_code_label <> 'unknown'
        group by category_code_label
        having count(distinct category_id) > 1
    )
),

revenue_shares as (
    select
        sum(price) as revenue,
        sum(price) filter (where category_top = 'unknown') as unknown_category_revenue,
        sum(price) filter (where brand_label = 'unknown') as unknown_brand_revenue
    from {{ ref('int_purchases') }}
),

session_counts as (
    select count(*) filter (where is_long_session) as long_sessions
    from {{ ref('int_sessions') }}
),

zero_price_pairs as (
    select count(*) filter (where is_zero_price_carted_pair) as pairs
    from {{ ref('int_session_products') }}
),

dedup as (
    select exact_duplicate_rows_removed from {{ ref('stg_dedup_audit') }}
),

metrics as (
    select 'exact_duplicate_rows_removed' as metric_key, 'Exact duplicate rows removed' as metric_label,
           'raw rows' as basis, cast(dd.exact_duplicate_rows_removed as double) as value,
           cast(s0.duplicates as double) as sprint0_raw_basis_value, 1 as sort_order
    from dedup as dd cross join s0
    union all
    select 'null_session_events_excluded', 'Events with a null session, excluded',
           'deduplicated events before session exclusions', d.null_session_events, s0.null_session_events, 2
    from dedup_before_exclusions as d cross join s0
    union all
    select 'multi_user_sessions_excluded', 'Sessions with more than one user_id, excluded',
           'deduplicated events before session exclusions', mu.multi_user_sessions, s0.multi_user_sessions, 3
    from multi_user as mu cross join s0
    union all
    select 'zero_price_events', 'Zero-price events', 'deduplicated events in valid sessions',
           ve.zero_price_events, s0.zero_price_events, 4
    from valid_event_counts as ve cross join s0
    union all
    select 'cart_events_with_no_view_at_or_before', 'Cart events with no view at or before them in the session',
           'deduplicated events in valid sessions', cn.cart_events_with_no_view_at_or_before, s0.cart_no_view, 5
    from cart_no_view as cn cross join s0
    union all
    select 'sessions_longer_than_24_hours', 'Sessions longer than 24 hours (kept)',
           'deduplicated events in valid sessions', sc.long_sessions, s0.long_sessions, 6
    from session_counts as sc cross join s0
    union all
    select 'unknown_category_events', 'Events with an unknown category', 'deduplicated events in valid sessions',
           ve.unknown_category_events, s0.unknown_category_events, 7
    from valid_event_counts as ve cross join s0
    union all
    select 'unknown_category_event_share', 'Unknown category share of events', 'deduplicated events in valid sessions',
           ve.unknown_category_events / ve.events, null, 8
    from valid_event_counts as ve
    union all
    select 'unknown_category_revenue_share', 'Unknown category share of revenue', 'deduplicated events in valid sessions',
           rs.unknown_category_revenue / rs.revenue, null, 9
    from revenue_shares as rs
    union all
    select 'unknown_brand_events', 'Events with an unknown brand', 'deduplicated events in valid sessions',
           ve.unknown_brand_events, s0.unknown_brand_events, 10
    from valid_event_counts as ve cross join s0
    union all
    select 'unknown_brand_event_share', 'Unknown brand share of events', 'deduplicated events in valid sessions',
           ve.unknown_brand_events / ve.events, null, 11
    from valid_event_counts as ve
    union all
    select 'unknown_brand_revenue_share', 'Unknown brand share of revenue', 'deduplicated events in valid sessions',
           rs.unknown_brand_revenue / rs.revenue, null, 12
    from revenue_shares as rs
    union all
    select 'category_codes_with_multiple_ids', 'Category codes mapping to more than one category_id',
           'deduplicated events in valid sessions', mi.codes, s0.multi_id_codes, 13
    from multi_id_codes as mi cross join s0
    union all
    select 'zero_price_carted_pairs', 'Carted pairs whose cart events are all zero-price (in pair counts, not in value)',
           'deduplicated events in valid sessions', zp.pairs, null, 14
    from zero_price_pairs as zp
),

-- Section 3: headline metrics with and without sessions longer than 24 hours.
{% set populations = [('all_valid_sessions', 'true'), ('excluding_long_sessions', 'not is_long_session')] %}
sensitivity_counts as (
    {% for population, condition in populations %}
    select
        '{{ population }}' as population,
        count(*) as sessions,
        count(*) filter (where has_view) as sessions_with_view,
        count(*) filter (where has_cart) as sessions_with_cart,
        count(*) filter (where has_purchase) as orders,
        count(*) filter (where has_view and has_cart) as viewing_sessions_with_cart,
        count(*) filter (where has_cart and has_purchase_of_carted_product) as cart_sessions_with_carted_product_purchase,
        sum(revenue) as revenue
    from {{ ref('int_session_facts') }}
    where {{ condition }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

sensitivity_rates as (
    select
        population,
        orders / sessions as session_purchase_rate,
        viewing_sessions_with_cart / sessions_with_view as view_to_cart_session_rate,
        cart_sessions_with_carted_product_purchase / sessions_with_cart as cart_session_purchase_rate,
        cast(revenue / sessions as double) as revenue_per_session,
        cast(revenue / orders as double) as average_order_value
    from sensitivity_counts
),

sensitivity as (
    {% set headline = [
        ('session_purchase_rate', 'Session purchase rate'),
        ('view_to_cart_session_rate', 'View-to-cart session rate'),
        ('cart_session_purchase_rate', 'Cart-session purchase rate'),
        ('revenue_per_session', 'Revenue per session'),
        ('average_order_value', 'Average order value'),
    ] %}
    {% for key, label in headline %}
    select
        'long_session_sensitivity:{{ key }}' as metric_key,
        '{{ label }}, long-session sensitivity' as metric_label,
        'deduplicated events in valid sessions' as basis,
        max({{ key }}) filter (where population = 'all_valid_sessions') as value,
        max({{ key }}) filter (where population = 'excluding_long_sessions') as value_excluding_long_sessions,
        {{ 100 + loop.index }} as sort_order
    from sensitivity_rates
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    metric_key,
    'data_quality' as metric_group,
    metric_label,
    basis,
    value,
    cast(null as double) as value_excluding_long_sessions,
    sprint0_raw_basis_value,
    sort_order
from metrics
union all
select
    metric_key,
    'long_session_sensitivity' as metric_group,
    metric_label,
    basis,
    value,
    value_excluding_long_sessions,
    cast(null as double) as sprint0_raw_basis_value,
    sort_order
from sensitivity
