-- metrics.md Section 7: carted value is grouped by the category on the pair's latest cart event.
-- Returns pairs whose cart events at the latest timestamp carry different categories; any row
-- fails the build, because the contract does not say which category wins.
with cart_events as (
    select e.user_session, e.product_id, e.event_time, e.category_top, e.category_code_label
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
    where e.event_type = 'cart'
),

latest as (
    select user_session, product_id, max(event_time) as latest_time
    from cart_events
    group by user_session, product_id
)

select c.user_session, c.product_id
from cart_events as c
inner join latest as l
    on c.user_session = l.user_session and c.product_id = l.product_id and c.event_time = l.latest_time
group by c.user_session, c.product_id
having count(distinct c.category_top) > 1 or count(distinct c.category_code_label) > 1
