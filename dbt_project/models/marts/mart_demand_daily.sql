-- mart_demand_daily: demand actually arrived, and what was completed.
select day, date, demand, completed
from {{ ref('stg_demand_daily') }}
