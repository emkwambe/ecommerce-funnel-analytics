-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), A items 2 and 3: the difference between
-- revenue (primary) and revenue with repeat purchase events collapsed, broken down over the repeat
-- purchase events. Every dimension places each repeat purchase event in exactly one group, so each
-- dimension's groups sum exactly to the difference (assert_revenue_gap_decomposition_reconciles).
-- The 'total' row carries the difference as published in mart_kpis_daily.
with repeats as (
    select * from {{ ref('int_repeat_purchase_events') }}
),

published as (
    select revenue, revenue_repeat_collapsed, revenue - revenue_repeat_collapsed as revenue_difference
    from {{ ref('mart_kpis_daily') }}
    where period_type = 'month'
),

assigned as (
    select 'time_since_previous_purchase' as dimension, time_group as group_key,
           time_group_label as group_label, time_group_sort as sort_order,
           user_session, product_id, price
    from repeats
    union all
    select 'price_vs_first_purchase', price_group, price_group_label, price_group_sort,
           user_session, product_id, price
    from repeats
    union all
    -- Category groups are ordered by value in the export, not here.
    select 'category_top', category_top, category_top, null,
           user_session, product_id, price
    from repeats
    union all
    select 'purchase_events_in_pair', pair_size_group, pair_size_group_label, pair_size_group_sort,
           user_session, product_id, price
    from repeats
    union all
    select 'time_by_price', time_group || '|' || price_group, time_group_label || ' · ' || price_group_label,
           time_group_sort * 10 + price_group_sort,
           user_session, product_id, price
    from repeats
),

grouped as (
    select
        dimension,
        group_key,
        any_value(group_label) as group_label,
        min(sort_order) as sort_order,
        count(*) as repeat_purchase_events,
        count(distinct (user_session, product_id)) as pairs,
        sum(price) as repeat_purchase_value
    from assigned
    group by dimension, group_key
),

-- Concentration diagnostic: the share of each group's value from its 10 largest pairs by that value.
pair_values as (
    select dimension, group_key, user_session, product_id, sum(price) as pair_value
    from assigned
    group by dimension, group_key, user_session, product_id
),

top_pairs as (
    select dimension, group_key, sum(pair_value) as top_10_pair_value
    from (
        select
            *,
            row_number() over (
                partition by dimension, group_key order by pair_value desc, user_session, product_id
            ) as value_rank
        from pair_values
    )
    where value_rank <= 10
    group by dimension, group_key
),

groups as (
    select
        g.dimension,
        g.group_key,
        g.group_label,
        g.sort_order,
        g.repeat_purchase_events,
        g.pairs,
        g.repeat_purchase_value,
        cast(g.repeat_purchase_value / p.revenue_difference as double) as share_of_difference,
        cast(t.top_10_pair_value / g.repeat_purchase_value as double) as top_10_pair_share
    from grouped as g
    inner join top_pairs as t using (dimension, group_key)
    cross join published as p
),

total as (
    select
        'total' as dimension,
        'all' as group_key,
        'All repeat purchase events' as group_label,
        0 as sort_order,
        (select count(*) from repeats) as repeat_purchase_events,
        (select count(distinct (user_session, product_id)) from repeats) as pairs,
        (select sum(price) from repeats) as repeat_purchase_value,
        cast(1 as double) as share_of_difference,
        cast(null as double) as top_10_pair_share
)

select
    dimension || ':' || group_key as row_key,
    x.*,
    p.revenue,
    p.revenue_repeat_collapsed,
    p.revenue_difference
from (select * from groups union all select * from total) as x
cross join published as p
