-- Intermediate: daily capacity after absenteeism, one row per day.
-- Marts read from here when they need capacity; the raw feed never
-- reaches a dashboard directly.
select
    day,
    date,
    analysts_scheduled,
    absent,
    analysts_available,
    productivity,
    capacity,
    completed,
    demand,
    backlog
from {{ ref('stg_demand_daily') }}
