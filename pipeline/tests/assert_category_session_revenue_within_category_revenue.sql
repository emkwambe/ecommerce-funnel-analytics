-- metrics.md Changes 2026-09-26 (Sprint 3 ranking), item 11: revenue per category-session covers a narrower
-- population than Section 9 category revenue, so its numerator is at most the category revenue, and the
-- repeat-collapsed numerator is at most the primary one. DECIMAL sums, so the comparisons are exact.
select r.category_level, r.category, r.revenue, r.revenue_collapsed, f.revenue as category_revenue
from {{ ref('mart_category_ranking_counts') }} as r
inner join {{ ref('mart_funnel_category') }} as f using (category_level, category)
where r.spec_key = 'C1' and (r.revenue > f.revenue or r.revenue_collapsed > r.revenue)
