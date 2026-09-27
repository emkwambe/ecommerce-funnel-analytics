-- Reconciliation (metrics.md Changes 2026-09-26, Sprint 3 ranking, item 5): at both levels, every category's
-- C1 category-sessions and those with a purchase equal the category funnel's funnel_pairs and
-- funnel_pairs_with_purchase, "unknown" included, and no category is on one side only. Categories whose events
-- include no view (funnel_pairs = 0) have no category-sessions by definition.
with ranking as (
    select category_level, category, category_sessions, category_sessions_with_purchase
    from {{ ref('mart_category_ranking_counts') }}
    where spec_key = 'C1'
),
funnel as (
    select category_level, category, funnel_pairs, funnel_pairs_with_purchase
    from {{ ref('mart_funnel_category') }}
    where funnel_pairs > 0
)
select coalesce(r.category_level, f.category_level) as category_level,
       coalesce(r.category, f.category) as category,
       r.category_sessions, f.funnel_pairs, r.category_sessions_with_purchase, f.funnel_pairs_with_purchase
from ranking as r
full outer join funnel as f using (category_level, category)
where r.category is null or f.category is null
   or r.category_sessions <> f.funnel_pairs
   or r.category_sessions_with_purchase <> f.funnel_pairs_with_purchase
