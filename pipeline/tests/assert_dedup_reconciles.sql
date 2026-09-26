-- Reconciliation: raw rows - removed exact duplicates = stg_events rows (metrics.md Section 2, D1).
select a.raw_rows, a.exact_duplicate_rows_removed, e.stg_rows
from {{ ref('stg_dedup_audit') }} as a
cross join (select count(*) as stg_rows from {{ ref('stg_events') }}) as e
where a.raw_rows - a.exact_duplicate_rows_removed <> e.stg_rows
