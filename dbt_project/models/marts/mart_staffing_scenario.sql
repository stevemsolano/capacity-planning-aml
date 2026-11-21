-- mart_staffing_scenario: backlog by queue, the input the simulator
-- prices (overtime vs. hire). The simulator itself lives in
-- src/simulate/simulator.py; this mart is its auditable input.
select day, date, queue, sla_days, demand, backlog, sla_ok
from {{ ref('stg_demand_by_queue') }}
