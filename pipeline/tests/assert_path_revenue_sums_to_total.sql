-- Reconciliation: revenue split by purchase path sums to total revenue, and path event counts
-- sum to all purchase events (metrics.md Section 5).
with paths as (
    select sum(revenue) as revenue, sum(purchase_events) as purchase_events, sum(revenue_share) as share
    from {{ ref('mart_purchase_paths') }}
),
total as (select sum(price) as revenue, count(*) as purchase_events from {{ ref('int_purchases') }})
select paths.revenue, total.revenue as total_revenue, paths.purchase_events, total.purchase_events as total_events
from paths cross join total
where paths.revenue <> total.revenue
   or paths.purchase_events <> total.purchase_events
   or abs(paths.share - 1) > 1e-9
