-- Reconciliation (A item 6, secondary case A-S2): the raw basis recomputed here equals the Sprint 0
-- profile.json figure, and the attributed parts account for the whole difference to the Section 10
-- count. A non-zero remainder fails the build; the Changes entry requires escalation, not a fix-up.
select *
from {{ ref('mart_cart_no_view_reconciliation') }}
where raw_basis_count <> sprint0_raw_basis_count
   or remainder <> 0
   or (select count(*) from {{ ref('mart_cart_no_view_reconciliation') }}) <> 1
