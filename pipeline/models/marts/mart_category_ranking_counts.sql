-- metrics.md Changes 2026-09-26 (Sprint 3 ranking), items 4, 5, 11, and 12: per (specification, level, category),
-- category-sessions, those with a purchase in the category, and the two revenue sums. The point values that
-- funnel.rankings checks its bootstrap input against, that assert_category_ranking_reconciles ties to the
-- category funnel, and that funnel.verify reproduces independently (R2). "unknown" is kept (item 3: its
-- category-sessions are published as an exclusion count); funnel.rankings never ranks it.
--   C1 all category-sessions (primary)        C6 excluding sessions longer than 24 hours
--   C7 excluding the most active users        C8 sessions with no event of a product with a missing code
with sessions as (
    select * from {{ ref('mart_category_sessions') }}
),

specs as (
    select 'C1' as spec_key, * from sessions
    union all
    select 'C6', * from sessions where not is_long_session
    union all
    select 'C7', * from sessions where not is_most_active_user
    union all
    select 'C8', * from sessions where not has_missing_code_event
)

select
    spec_key || ':' || category_level || ':' || category as row_key,
    spec_key,
    category_level,
    category,
    count(*) as category_sessions,
    count(*) filter (where has_purchase) as category_sessions_with_purchase,
    sum(revenue) as revenue,
    sum(revenue_collapsed) as revenue_collapsed,
    count(distinct user_id) as users
from specs
group by spec_key, category_level, category
