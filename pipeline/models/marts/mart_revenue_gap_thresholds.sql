-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), A item 4: threshold sensitivity. For each
-- threshold T fixed in the Changes entry, the share of the revenue difference from repeat purchase
-- events whose time since the pair's previous purchase event is at most T.
with repeats as (
    select * from {{ ref('int_repeat_purchase_events') }}
),

thresholds (threshold_seconds, threshold_label) as (
    values
        (0, '0 s'), (1, '1 s'), (5, '5 s'), (10, '10 s'), (30, '30 s'), (60, '60 s'),
        (300, '5 min'), (1800, '30 min'), (3600, '1 h')
),

total as (
    select sum(price) as revenue_difference, count(*) as repeat_purchase_events from repeats
)

select
    t.threshold_seconds,
    t.threshold_label,
    count(r.event_id) as repeat_purchase_events_within,
    coalesce(sum(r.price), 0) as repeat_purchase_value_within,
    cast(coalesce(sum(r.price), 0) / any_value(tot.revenue_difference) as double) as share_of_difference,
    any_value(tot.repeat_purchase_events) as repeat_purchase_events,
    any_value(tot.revenue_difference) as revenue_difference
from thresholds as t
cross join total as tot
left join repeats as r on r.seconds_since_previous_purchase <= t.threshold_seconds
group by t.threshold_seconds, t.threshold_label
