-- metrics.md Changes 2026-09-26 (Sprint 2 investigations), A item 6 (secondary case A-S2): from the
-- Sprint 0 raw-basis count of cart events with no view at or before them in the session to the
-- Section 10 count, attributed in the order the entry fixes:
--   (i)   cart events in null-session events or in multi-user sessions, on raw rows;
--   (ii)  of the rest, cart rows removed as exact duplicates by D1;
--   (iii) a remainder, which assert_cart_no_view_reconciliation requires to be zero.
-- The raw basis is recomputed here as funnel.profile defined it (raw rows, non-null session and
-- product, a view of the pair at or before the cart time) and must equal the committed profile.json.
-- Null-session rows are outside that basis by its definition, so part (i)'s null-session count is
-- zero by construction; it is computed, not assumed.
{% set profile_json = env_var('FUNNEL_REPO_ROOT', 'C:/Dev/ecommerce-funnel-analytics') ~ '/ai-workflow/evidence/sprint-0/profile.json' %}

with raw as (
    select * from {{ source('raw', 'events_oct_2019') }}
),

raw_carts as (
    select * from raw
    where event_type = 'cart' and user_session is not null and product_id is not null
),

-- Views only for pairs that have cart rows, as in funnel.profile, to keep the anti-join small.
raw_views as (
    select user_session, product_id, event_time
    from raw
    where event_type = 'view'
      and (user_session, product_id) in (select (user_session, product_id) from raw_carts)
),

raw_basis as (
    select c.*
    from raw_carts as c
    where not exists (
        select 1 from raw_views as v
        where true
          and v.user_session = c.user_session
          and v.product_id = c.product_id
          and v.event_time <= c.event_time
    )
),

multi_user_sessions as (
    select user_session
    from raw
    where user_session is not null
    group by user_session
    having min(user_id) <> max(user_id)
),

classified as (
    select
        b.*,
        b.user_session is null as in_null_session,
        m.user_session is not null as in_multi_user_session
    from raw_basis as b
    left join multi_user_sessions as m using (user_session)
),

in_valid_sessions as (
    select * from classified where not in_null_session and not in_multi_user_session
),

sprint0 as (
    select cast(json_extract(content, '$.ordering_anomalies.cart_events_with_no_view_at_or_before_in_session') as bigint)
        as raw_basis_count
    from read_text('{{ profile_json }}')
),

contract as (
    select cast(value as bigint) as contract_basis_count
    from {{ ref('mart_data_quality') }}
    where metric_key = 'cart_events_with_no_view_at_or_before'
),

parts as (
    select
        (select raw_basis_count from sprint0) as sprint0_raw_basis_count,
        (select count(*) from classified) as raw_basis_count,
        (select count(*) filter (where in_null_session) from classified) as in_null_session_events,
        (select count(*) filter (where in_multi_user_session) from classified) as in_multi_user_sessions,
        (select count(*) from in_valid_sessions)
            - (select count(*) from (
                  select distinct event_time, event_type, product_id, category_id, category_code,
                                  brand, price, user_id, user_session
                  from in_valid_sessions
              )) as removed_as_exact_duplicates,
        (select contract_basis_count from contract) as contract_basis_count
)

select
    'cart_events_with_no_view_at_or_before' as row_key,
    *,
    raw_basis_count - contract_basis_count as difference,
    raw_basis_count - in_null_session_events - in_multi_user_sessions - removed_as_exact_duplicates
        - contract_basis_count as remainder
from parts
