-- Value sums use price_amount (DECIMAL(18, 2)) so reconciliation is exact. Returns events whose
-- logged price is not exactly representable with two decimals; any row fails the build.
select event_id, price, price_amount
from {{ ref('stg_events') }}
where cast(price_amount as double) <> price
