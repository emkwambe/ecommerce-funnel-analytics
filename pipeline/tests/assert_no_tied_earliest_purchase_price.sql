-- metrics.md Section 4 (secondary revenue): the price on the earliest purchase event of each
-- (session, product) pair. Returns pairs whose purchase events at the earliest timestamp carry
-- different prices; any row fails the build, because the contract does not say which price wins.
with purchase_events as (
    select e.user_session, e.product_id, e.event_time, e.price
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
    where e.event_type = 'purchase'
),

earliest as (
    select user_session, product_id, min(event_time) as earliest_time
    from purchase_events
    group by user_session, product_id
)

select p.user_session, p.product_id, count(distinct p.price) as distinct_prices
from purchase_events as p
inner join earliest as f
    on p.user_session = f.user_session and p.product_id = f.product_id and p.event_time = f.earliest_time
group by p.user_session, p.product_id
having count(distinct p.price) > 1
