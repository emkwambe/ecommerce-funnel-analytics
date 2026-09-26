-- One row per deduplicated event (metrics.md Section 2, D1): exact duplicate rows are
-- removed; rows that differ in any column are kept as logged.
with deduplicated as (
    select distinct
        event_time, event_type, product_id, category_id, category_code,
        brand, price, user_id, user_session
    from {{ source('raw', 'events_oct_2019') }}
),

labeled as (
    select
        *,
        nullif(trim(category_code), '') as category_code_clean,
        nullif(trim(brand), '') as brand_clean
    from deduplicated
)

select
    row_number() over () as event_id,
    event_time,
    event_type,
    product_id,
    category_id,
    category_code,
    brand,
    price,
    cast(price as decimal(18, 2)) as price_amount,
    user_id,
    user_session,
    price = 0 as is_zero_price,
    case
        when category_code_clean is null then 'unknown'
        else split_part(category_code_clean, '.', 1)
    end as category_top,
    coalesce(category_code_clean, 'unknown') as category_code_label,
    coalesce(brand_clean, 'unknown') as brand_label
from labeled
