-- Staging: per-queue demand split (see docs/metric-definitions.md
-- for the pro-rata allocation rule).
select
    cast(day as integer) as day,
    cast(date as date) as date,
    queue,
    cast(sla_days as integer) as sla_days,
    cast(demand as integer) as demand,
    cast(backlog as integer) as backlog,
    cast(sla_ok as boolean) as sla_ok
from {{ source('raw', 'raw_demand_by_queue') }}
