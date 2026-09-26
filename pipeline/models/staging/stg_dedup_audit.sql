-- Raw row count and exact duplicate rows removed (metrics.md Section 2, D1; Section 10).
-- Counted on raw rows, independently of stg_events: surplus rows beyond the first in each
-- group of identical rows.
with raw as (
    select * from {{ source('raw', 'events_oct_2019') }}
),

identical_groups as (
    select count(*) as n
    from raw
    group by
        event_time, event_type, product_id, category_id, category_code,
        brand, price, user_id, user_session
)

select
    (select count(*) from raw) as raw_rows,
    coalesce(sum(n - 1) filter (where n > 1), 0) as exact_duplicate_rows_removed,
    count(*) filter (where n > 1) as exact_duplicate_groups
from identical_groups
