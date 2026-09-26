-- int_later_purchase_spec_pairs grain: each pair appears at most once per specification.
select spec_key, pair_key, count(*) as n
from {{ ref('int_later_purchase_spec_pairs') }}
group by spec_key, pair_key
having count(*) > 1
