-- mart_capacity_daily: capacity available after absenteeism.
-- Utilisation lives here, not in the dashboard: completed / capacity.
select
    day,
    date,
    analysts_scheduled,
    absent,
    analysts_available,
    productivity,
    capacity,
    completed,
    round(completed * 1.0 / nullif(capacity, 0), 3) as utilisation
from {{ ref('stg_demand_daily') }}
