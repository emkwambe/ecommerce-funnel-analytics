-- Changes 2026-09-26 (Sprint 2 investigations), common rules (intervals): per (specification, user_id), the sums
-- the user-level cluster bootstrap resamples (funnel.later_purchases). Not exported to the site.
select
    spec_key || ':' || cast(user_id as varchar) as row_key,
    spec_key,
    user_id,
    count(*) as eligible_pairs,
    count(*) filter (where is_followed) as followed_pairs,
    coalesce(sum(value), 0) as eligible_value,
    coalesce(sum(value) filter (where is_followed), 0) as followed_value
from {{ ref('int_later_purchase_spec_pairs') }}
group by spec_key, user_id
