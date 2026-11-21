# Orchestration — Prefect here, Airflow as a documented variant

## Prefect (what runs in this repo)
Flow `capacity_pipeline`: generate → load → build marts → simulate.
Retries, logs, schedule (daily 06:00 ET in GitHub Actions / Prefect Cloud free).
Python-native, no scheduler + webserver + database just to demo it.

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
