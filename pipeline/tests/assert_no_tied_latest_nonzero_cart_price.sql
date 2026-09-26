-- metrics.md Section 7: carted value uses the price on the latest non-zero cart event of the pair.
-- The contract does not say which price wins when two non-zero cart events of a pair share the
-- latest timestamp at different prices. Returns such pairs; any row fails the build.
with cart_events as (
    select e.user_session, e.product_id, e.event_time, e.price
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
    where e.event_type = 'cart' and e.price > 0
),

latest as (
    select user_session, product_id, max(event_time) as latest_time
    from cart_events
    group by user_session, product_id
)

select c.user_session, c.product_id, count(distinct c.price) as distinct_prices
from cart_events as c
inner join latest as l
    on c.user_session = l.user_session and c.product_id = l.product_id and c.event_time = l.latest_time
group by c.user_session, c.product_id
having count(distinct c.price) > 1
