-- Reconciliation (A item 5, secondary case A-S1): the breakdown of exact duplicate rows by event type
-- and group size sums to the rows removed by D1 (stg_dedup_audit), and its groups to the audit's groups.
select b.rows_removed, b.duplicate_groups, a.exact_duplicate_rows_removed, a.exact_duplicate_groups
from (select sum(rows_removed) as rows_removed, sum(duplicate_groups) as duplicate_groups
      from {{ ref('mart_duplicate_rows_breakdown') }}) as b
cross join {{ ref('stg_dedup_audit') }} as a
where b.rows_removed <> a.exact_duplicate_rows_removed
   or b.duplicate_groups <> a.exact_duplicate_groups
