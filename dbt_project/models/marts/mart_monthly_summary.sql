-- mart_monthly_summary: the planning grain. Daily rows are the engine;
-- managers plan by month. One row per calendar month.
-- Built from int_daily_capacity (demand + capacity + backlog in one place);
-- SLA breach = backlog >= 5,000, the same rule as mart_backlog_sla.
select
    date_trunc('month', date) as month,
    count(*) as days,
    sum(demand) as demand,
    sum(completed) as completed,
    sum(capacity) as capacity,
    max(backlog) as peak_backlog,
    sum(case when backlog >= 5000 then 1 else 0 end) as sla_breach_days
from {{ ref('int_daily_capacity') }}
group by 1
order by 1
