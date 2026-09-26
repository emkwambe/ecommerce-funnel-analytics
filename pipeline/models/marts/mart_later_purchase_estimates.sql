-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), B items 9-11, 13, and 14: point estimates per
-- specification, with the counts and value sums behind every share (owner decision H3-D2). Intervals come
-- from the user-level cluster bootstrap in funnel.later_purchases (H3-D5), not from this model. Pairs whose
-- value is null (all-zero-price cart or view events) count in the count share and not in the value share.
select
    spec_key,
    any_value(pair_type) as pair_type,
    any_value(window_days) as window_days,
    any_value(cutoff) as cutoff,
    count(*) as eligible_pairs,
    count(*) filter (where is_followed) as followed_pairs,
    cast(count(*) filter (where is_followed) as double) / count(*) as count_share,
    count(value) as eligible_pairs_with_value,
    coalesce(sum(value), 0) as eligible_value,
    coalesce(sum(value) filter (where is_followed), 0) as followed_value,
    cast(coalesce(sum(value) filter (where is_followed), 0) / sum(value) as double) as value_share,
    count(distinct user_id) as users
from {{ ref('int_later_purchase_spec_pairs') }}
group by spec_key
