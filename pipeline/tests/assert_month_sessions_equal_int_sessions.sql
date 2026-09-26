-- Reconciliation: month-total sessions in mart_kpis_daily = int_sessions rows, and the daily rows
-- sum to the same count (metrics.md Sections 3 and 6).
with s as (select count(*) as sessions from {{ ref('int_sessions') }}),
m as (select sessions from {{ ref('mart_kpis_daily') }} where period_type = 'month'),
d as (select sum(sessions) as sessions from {{ ref('mart_kpis_daily') }} where period_type = 'day')
select s.sessions as int_sessions, m.sessions as month_sessions, d.sessions as daily_sessions_sum
from s cross join m cross join d
where s.sessions <> m.sessions or s.sessions <> d.sessions
