-- Reconciliation (Changes 2026-09-26, second entry, item 2): at each category level, category
-- revenue and purchase events sum to the totals in int_purchases, and category events sum to all
-- deduplicated events in valid sessions. DECIMAL sums, so equality is exact.
with totals as (
    select sum(price) as revenue, count(*) as purchase_events from {{ ref('int_purchases') }}
),
valid_events as (
    select count(*) as events
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
),
by_level as (
    select category_level, sum(revenue) as revenue, sum(purchase_events) as purchase_events, sum(events) as events
    from {{ ref('mart_funnel_category') }}
    group by category_level
)
select b.*, t.revenue as total_revenue, t.purchase_events as total_purchase_events, v.events as total_events
from by_level as b cross join totals as t cross join valid_events as v
where b.revenue <> t.revenue or b.purchase_events <> t.purchase_events or b.events <> v.events
   or (select count(distinct category_level) from {{ ref('mart_funnel_category') }}) <> 2
