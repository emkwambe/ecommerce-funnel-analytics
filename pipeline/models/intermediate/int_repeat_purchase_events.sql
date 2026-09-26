-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), A items 1 and 3: one row per repeat
-- purchase event, meaning every purchase event of a (valid session, product) pair except one at the
-- pair's earliest purchase timestamp. Which tied earliest event is kept does not change any value:
-- assert_no_tied_earliest_purchase_price guarantees one price at that timestamp.
with purchases as (
    select event_id, user_session, product_id, event_time, price, category_top
    from {{ ref('int_purchases') }}
),

repeated_pairs as (
    select user_session, product_id, count(*) as purchase_events_in_pair
    from purchases
    group by user_session, product_id
    having count(*) > 1
),

ranked as (
    select
        p.*,
        r.purchase_events_in_pair,
        row_number() over (
            partition by p.user_session, p.product_id order by p.event_time, p.event_id
        ) as position_in_pair
    from purchases as p
    inner join repeated_pairs as r using (user_session, product_id)
),

-- Item 3: the pair's previous purchase event is the latest *other* purchase event of the pair at or
-- before this one, so events tied on a timestamp are 0 s apart whatever their order.
previous as (
    select a.event_id, max(b.event_time) as previous_purchase_time
    from ranked as a
    inner join ranked as b
        on a.user_session = b.user_session
        and a.product_id = b.product_id
        and b.event_id <> a.event_id
        and b.event_time <= a.event_time
    group by a.event_id
),

repeats as (
    select
        r.event_id,
        r.user_session,
        r.product_id,
        r.event_time,
        r.price,
        r.category_top,
        r.purchase_events_in_pair,
        sp.earliest_purchase_price as first_purchase_price,
        pv.previous_purchase_time,
        date_diff('second', pv.previous_purchase_time, r.event_time) as seconds_since_previous_purchase
    from ranked as r
    inner join previous as pv using (event_id)
    inner join {{ ref('int_session_products') }} as sp using (user_session, product_id)
    where r.position_in_pair > 1
)

select
    *,
    case
        when seconds_since_previous_purchase = 0 then 'same_second'
        when seconds_since_previous_purchase < 60 then 'under_a_minute'
        else 'a_minute_or_more'
    end as time_group,
    case
        when seconds_since_previous_purchase = 0 then 'Same second'
        when seconds_since_previous_purchase < 60 then '1 to 59 seconds later'
        else '1 minute or more later'
    end as time_group_label,
    case
        when seconds_since_previous_purchase = 0 then 1
        when seconds_since_previous_purchase < 60 then 2
        else 3
    end as time_group_sort,
    case when price = first_purchase_price then 'same_price' else 'different_price' end as price_group,
    case
        when price = first_purchase_price then 'Same price as the first purchase event'
        else 'Different price from the first purchase event'
    end as price_group_label,
    case when price = first_purchase_price then 1 else 2 end as price_group_sort,
    case
        when purchase_events_in_pair = 2 then '2'
        when purchase_events_in_pair = 3 then '3'
        else '4_or_more'
    end as pair_size_group,
    case
        when purchase_events_in_pair = 2 then '2'
        when purchase_events_in_pair = 3 then '3'
        else '4 or more'
    end as pair_size_group_label,
    least(purchase_events_in_pair, 4) - 1 as pair_size_group_sort
from repeats
