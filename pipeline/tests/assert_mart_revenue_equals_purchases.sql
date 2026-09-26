-- Reconciliation: mart revenue = sum of purchase prices in int_purchases, for the month row and
-- for the sum of the daily rows (metrics.md Section 4). Sums are DECIMAL, so equality is exact.
with purchases as (select sum(price) as revenue from {{ ref('int_purchases') }}),
month_row as (select revenue from {{ ref('mart_kpis_daily') }} where period_type = 'month'),
day_rows as (select sum(revenue) as revenue from {{ ref('mart_kpis_daily') }} where period_type = 'day')
select p.revenue as purchases_revenue, m.revenue as month_revenue, d.revenue as daily_revenue_sum
from purchases as p cross join month_row as m cross join day_rows as d
where p.revenue <> m.revenue or p.revenue <> d.revenue
   or (select count(*) from {{ ref('mart_kpis_daily') }} where period_type = 'month') <> 1
