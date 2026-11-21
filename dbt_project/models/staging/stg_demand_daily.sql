-- Staging: one clean copy of the generated daily feed.
-- Source is raw_demand_daily (loaded from data/raw/demand_daily.csv).
-- No business logic here — only types and naming.
select
    cast(day as integer) as day,
    cast(date as date) as date,
    weekday,
    cast(demand as integer) as demand,
    cast(analysts_scheduled as integer) as analysts_scheduled,
    cast(absent as integer) as absent,
    cast(analysts as integer) as analysts_available,
    cast(productivity as double) as productivity,
    cast(capacity as integer) as capacity,
    cast(completed as integer) as completed,
    cast(backlog as integer) as backlog,
    cast(sla_ok as boolean) as sla_ok
from {{ source('raw', 'raw_demand_daily') }}
