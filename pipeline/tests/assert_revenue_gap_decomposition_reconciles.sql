-- Reconciliation (metrics.md Changes 2026-09-26, Sprint 2 investigations, A items 2 and 3):
-- 1. the repeat purchase events' price sum equals revenue (primary) minus revenue with repeat purchase
--    events collapsed, as published in mart_kpis_daily;
-- 2. their count equals the surplus purchase events of int_session_products;
-- 3. every dimension's groups sum exactly (DECIMAL) to the difference and to the event count.
-- Any returned row fails the build.
with total as (
    select repeat_purchase_events, repeat_purchase_value, revenue_difference
    from {{ ref('mart_revenue_gap_decomposition') }}
    where dimension = 'total'
),

surplus as (
    select sum(purchase_event_count - 1) as surplus_purchase_events
    from {{ ref('int_session_products') }}
    where is_purchased
),

dimensions as (
    select dimension, sum(repeat_purchase_value) as value, sum(repeat_purchase_events) as events
    from {{ ref('mart_revenue_gap_decomposition') }}
    where dimension <> 'total'
    group by dimension
)

select 'total value <> published difference' as failure, null as dimension
from total where repeat_purchase_value <> revenue_difference
union all
select 'total events <> surplus purchase events', null
from total cross join surplus where total.repeat_purchase_events <> surplus.surplus_purchase_events
union all
select 'dimension does not sum to the difference', d.dimension
from dimensions as d cross join total as t
where d.value <> t.revenue_difference or d.events <> t.repeat_purchase_events
union all
select 'expected five dimensions', null
where (select count(*) from dimensions) <> 5
   or (select count(*) from total) <> 1
