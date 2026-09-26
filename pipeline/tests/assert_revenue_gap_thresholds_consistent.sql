-- Threshold sensitivity (A item 4) is consistent with the decomposition: the 0 s share equals the
-- "Same second" group's share, shares never decrease as the threshold grows, none exceeds 1, and every
-- threshold row uses the same difference as the decomposition's total row.
with t as (
    select *, lag(repeat_purchase_value_within) over (order by threshold_seconds) as previous_value
    from {{ ref('mart_revenue_gap_thresholds') }}
),

same_second as (
    select coalesce(max(repeat_purchase_value) filter (where group_key = 'same_second'), 0) as value
    from {{ ref('mart_revenue_gap_decomposition') }}
    where dimension = 'time_since_previous_purchase'
),

total as (
    select revenue_difference from {{ ref('mart_revenue_gap_decomposition') }} where dimension = 'total'
)

select threshold_label, 'decreasing' as failure from t where repeat_purchase_value_within < previous_value
union all
select threshold_label, 'exceeds the difference' from t cross join total
where t.repeat_purchase_value_within > total.revenue_difference
union all
select threshold_label, 'difference differs from the decomposition' from t cross join total
where t.revenue_difference <> total.revenue_difference
union all
select threshold_label, '0 s differs from the same-second group' from t cross join same_second
where t.threshold_seconds = 0 and t.repeat_purchase_value_within <> same_second.value
union all
select null, 'expected nine thresholds' where (select count(*) from t) <> 9
