-- mart_backlog_sla: THE single definition of backlog and SLA.
-- Change the definition here, not in five dashboards.
-- SLA rule (docs/metric-definitions.md): backlog < 5,000 = sla_ok.
select
    day,
    date,
    demand,
    completed,
    backlog,
    backlog < 5000 as sla_ok
from {{ ref('stg_demand_daily') }}
