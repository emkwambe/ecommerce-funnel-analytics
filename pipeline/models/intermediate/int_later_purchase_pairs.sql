-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), B items 7, 8, 12, 13, and 16. One row per pair
-- that analysis B follows up, with no cutoff applied (the marts apply the cutoffs):
--   pair_type 'carted': carted pairs with no purchase event of that product in the session (the Section 7
--     population of carted value with no observed purchase in this session);
--   pair_type 'viewed': pairs with at least one view event, no cart event, and no purchase event in the
--     session, kept only in sessions that also hold a 'carted' pair (item 13 restricts them further).
-- anchor_time is the pair's latest cart event ('carted') or latest view event ('viewed'), and value its
-- latest non-zero cart or view price (null when there is none; excluded from value shares).
-- first_later_purchase_time is the earliest purchase event of the same product by the same user_id that
-- meets item 8 conditions 1-3 (no window: the marts and funnel.later_purchases apply condition 4):
--   (1) a different valid session of the same user_id; (2) that session starts after this session starts;
--   (3) the event time is strictly after anchor_time.
-- first_purchase_time_any_session_start drops condition 2 (item 16, overlapping-session diagnostic).
with valid_events as (
    select e.user_session, e.product_id, e.event_type, e.event_time, e.price, e.price_amount
    from {{ ref('stg_events') }} as e
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

carted as (
    select
        'carted' as pair_type,
        sp.user_session,
        sp.product_id,
        sp.latest_cart_time as anchor_time,
        sp.latest_nonzero_cart_price as value
    from {{ ref('int_session_products') }} as sp
    where sp.is_carted and not sp.is_purchased
),

sessions_with_carted as (
    select distinct user_session from carted
),

viewed as (
    select
        'viewed' as pair_type,
        v.user_session,
        v.product_id,
        max(v.event_time) filter (where v.event_type = 'view') as anchor_time,
        arg_max(v.price_amount, v.event_time) filter (where v.event_type = 'view' and v.price > 0) as value
    from valid_events as v
    inner join sessions_with_carted using (user_session)
    group by v.user_session, v.product_id
    having count(*) filter (where v.event_type = 'view') > 0
       and count(*) filter (where v.event_type in ('cart', 'purchase')) = 0
),

pairs as (
    select p.*, s.user_id, s.session_start, s.is_long_session
    from (select * from carted union all select * from viewed) as p
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

user_purchases as (
    select p.user_session, p.product_id, p.event_time, s.user_id, s.session_start as purchase_session_start
    from {{ ref('int_purchases') }} as p
    inner join {{ ref('int_sessions') }} as s using (user_session)
),

later as (
    select
        pr.pair_type,
        pr.user_session,
        pr.product_id,
        min(pu.event_time) filter (where pu.purchase_session_start > pr.session_start) as first_later_purchase_time,
        min(pu.event_time) as first_purchase_time_any_session_start
    from pairs as pr
    inner join user_purchases as pu
        on pu.user_id = pr.user_id
        and pu.product_id = pr.product_id
        and pu.user_session <> pr.user_session
        and pu.event_time > pr.anchor_time
    group by pr.pair_type, pr.user_session, pr.product_id
)

select
    pr.pair_type || ':' || pr.user_session || ':' || cast(pr.product_id as varchar) as pair_key,
    pr.pair_type,
    pr.user_session,
    pr.product_id,
    pr.user_id,
    pr.session_start,
    pr.is_long_session,
    pr.anchor_time,
    pr.value,
    l.first_later_purchase_time,
    l.first_purchase_time_any_session_start
from pairs as pr
left join later as l using (pair_type, user_session, product_id)
