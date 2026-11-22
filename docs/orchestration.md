# Orchestration — Prefect here, Airflow as a documented variant

## Prefect (what runs in this repo)
Flow `capacity_pipeline`: generate → load → build marts → simulate.
Retries and logs come from Prefect when it is installed; without it the
flow runs as plain functions with identical logic. Python-native, no
scheduler + webserver + database just to demo it.

## The daily run (real, not a plan)
`.github/workflows/scheduled.yml` runs every day at 11:00 UTC (06:00 EST,
07:00 EDT in summer) and on manual dispatch: generate → pipeline →
`dbt build` → pytest, with the run log public in the repo's Actions tab.
Prefect Cloud (free tier) is the documented alternative for the same
schedule, not a second live run. If a run goes red, the log shows which
step failed — there is no silent schedule.

## Airflow (1:1 mapping, not a second pipeline)
Same DAG, same tasks, same order. If a JD asks for Airflow explicitly:
- `generate` → PythonOperator, `load` → PythonOperator,
  `dbt run` → BashOperator, `simulate` → PythonOperator.
- Schedule, retries, and dependencies map 1:1. No second pipeline is
  maintained — the README states this so a reviewer does not have to guess.

## Autosys (enterprise scheduling, banking)
Scheduler for batch jobs with dependencies and calendars, widely used in
banking. It is NOT a modern data orchestrator: no lineage, no data tests,
and it cannot be demoed in a public repo (server + licence, no free tier).
In production banking this pipeline's daily run would be scheduled in
Autosys; in this repo Prefect + GitHub Actions demonstrate the same
scheduling, observability, and failure handling.
