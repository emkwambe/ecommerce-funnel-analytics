-- mart_category_sessions grain: one row per (level, valid session, category).
select category_level, user_session, category, count(*) as n
from {{ ref('mart_category_sessions') }}
group by category_level, user_session, category
having count(*) > 1
