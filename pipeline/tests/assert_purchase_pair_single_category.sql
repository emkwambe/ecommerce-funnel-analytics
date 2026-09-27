-- mart_category_sessions takes a (session, product) purchase pair's category from its earliest purchase event
-- (Section 4, repeat purchase events collapsed). That choice is safe only if every purchase event of the pair
-- carries the same category at both levels.
select e.user_session, e.product_id,
       count(distinct e.category_top) as top_levels, count(distinct e.category_code_label) as codes
from {{ ref('stg_events') }} as e
inner join {{ ref('int_sessions') }} as s using (user_session)
where e.event_type = 'purchase' and not e.is_zero_price
group by e.user_session, e.product_id
having count(distinct e.category_top) > 1 or count(distinct e.category_code_label) > 1
