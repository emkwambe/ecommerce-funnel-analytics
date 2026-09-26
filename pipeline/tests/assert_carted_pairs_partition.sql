-- Reconciliation (metrics.md Section 7): carted pairs with no observed purchase + carted pairs with
-- a purchase = carted pairs, in every category row; and at each level the carted pairs sum to all
-- carted pairs in int_session_products.
with total as (
    select count(*) as carted_pairs from {{ ref('int_session_products') }} where is_carted
),
row_failures as (
    select category_key, 'row partition' as failure
    from {{ ref('mart_funnel_category') }}
    where carted_pairs_with_no_observed_purchase + carted_pairs_with_purchase <> carted_pairs
),
level_failures as (
    select m.category_level as category_key, 'level total' as failure
    from {{ ref('mart_funnel_category') }} as m cross join total as t
    group by m.category_level, t.carted_pairs
    having sum(m.carted_pairs) <> t.carted_pairs
)
select * from row_failures
union all
select * from level_failures
