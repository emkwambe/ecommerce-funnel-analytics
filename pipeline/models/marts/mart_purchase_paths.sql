-- metrics.md Section 5: purchase event counts, revenue, and revenue share per purchase path.
with totals as (
    select sum(price) as total_revenue
    from {{ ref('int_purchases') }}
)

select
    p.purchase_path,
    count(*) as purchase_events,
    sum(p.price) as revenue,
    sum(p.price) / any_value(t.total_revenue) as revenue_share
from {{ ref('int_purchases') }} as p
cross join totals as t
group by p.purchase_path
