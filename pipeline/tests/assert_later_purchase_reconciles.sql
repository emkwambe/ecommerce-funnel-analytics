-- Reconciliation (metrics.md Changes 2026-09-26, Sprint 2 investigations, B):
-- 1. per specification, the user-level sums the bootstrap resamples add up to the point estimates;
-- 2. the Kaplan-Meier population (every carted pair with no purchase in the session) carries exactly the
--    published carted value with no observed purchase in this session (Section 7, mart_funnel_category);
-- 3. the Kaplan-Meier pairs from sessions starting by the 7-day cutoff are exactly B1's eligible pairs, and
--    those with an event before 7 days are exactly B1's followed pairs (the fixed window and the survival
--    data agree pair for pair, before any estimation).
-- Any returned row fails the build.
with estimates as (
    select * from {{ ref('mart_later_purchase_estimates') }}
),

user_sums as (
    select spec_key, sum(eligible_pairs) as eligible_pairs, sum(followed_pairs) as followed_pairs,
           sum(eligible_value) as eligible_value, sum(followed_value) as followed_value
    from {{ ref('mart_later_purchase_user_sums') }}
    group by spec_key
),

km as (
    select * from {{ ref('mart_later_purchase_km_pairs') }}
),

published_carted_value as (
    select sum(carted_value_with_no_observed_purchase) as value
    from {{ ref('mart_funnel_category') }}
    where category_level = 'category_top'
),

km_b1 as (
    select count(*) as eligible_pairs,
           count(*) filter (where is_event and duration_seconds < 7 * 86400) as followed_pairs
    from km where cohort = 'by_7_day_cutoff'
)

select 'user sums differ from estimates' as failure, e.spec_key
from estimates as e
left join user_sums as u using (spec_key)
where u.spec_key is null
   or e.eligible_pairs <> u.eligible_pairs or e.followed_pairs <> u.followed_pairs
   or e.eligible_value <> u.eligible_value or e.followed_value <> u.followed_value
union all
select 'KM population value differs from the published carted value', null
from published_carted_value as p
where p.value <> (select coalesce(sum(value), 0) from km)
union all
select 'KM by-cutoff cohort differs from B1', null
from km_b1 cross join (select * from estimates where spec_key = 'B1') as b1
where km_b1.eligible_pairs <> b1.eligible_pairs or km_b1.followed_pairs <> b1.followed_pairs
union all
select 'expected seven specifications', null
where (select count(*) from estimates) <> 7
