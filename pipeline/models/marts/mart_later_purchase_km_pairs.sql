-- Changes 2026-09-26 (Sprint 2 investigations), B item 12 (Kaplan-Meier, R3): every carted pair with no purchase
-- event of that product in the session, with no cutoff. Time runs from the cart session's start to the pair's
-- first later purchase (item 8, conditions 1-3); a pair with none is censored at 2019-10-31 23:59:59 UTC.
-- cohort splits pairs at the 7-day cutoff for the cohort diagnostic (owner decision B-D6). Read by
-- funnel.later_purchases; not exported to the site.
select
    pair_key,
    user_id,
    session_start,
    value,
    first_later_purchase_time is not null as is_event,
    date_diff(
        'second', session_start, coalesce(first_later_purchase_time, timestamp '2019-10-31 23:59:59')
    ) as duration_seconds,
    case when session_start <= timestamp '2019-10-24 23:59:59' then 'by_7_day_cutoff' else 'after_7_day_cutoff' end
        as cohort
from {{ ref('int_later_purchase_pairs') }}
where pair_type = 'carted'
