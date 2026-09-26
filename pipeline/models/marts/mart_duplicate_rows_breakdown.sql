-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), A item 5 (secondary case A-S1): the exact
-- duplicate rows removed by D1, by event type and by the size of their group of identical rows.
-- Counts only, on raw rows (Section 10). Rows sum to stg_dedup_audit.exact_duplicate_rows_removed
-- (assert_duplicate_rows_breakdown_reconciles). Grouping on every column puts nulls together, as in
-- stg_dedup_audit.
with identical_groups as (
    select event_type, count(*) as group_rows
    from {{ source('raw', 'events_oct_2019') }}
    group by
        event_time, event_type, product_id, category_id, category_code,
        brand, price, user_id, user_session
    having count(*) > 1
)

select
    event_type || ':' || case when group_rows = 2 then '2' when group_rows = 3 then '3' else '4_or_more' end
        as row_key,
    event_type,
    case when group_rows = 2 then '2' when group_rows = 3 then '3' else '4_or_more' end as group_size,
    case when group_rows = 2 then '2' when group_rows = 3 then '3' else '4 or more' end as group_size_label,
    count(*) as duplicate_groups,
    cast(sum(group_rows - 1) as bigint) as rows_removed
from identical_groups
group by all
