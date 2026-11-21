# Tableau — what to build, and what is NOT automated

## The honest split
- **Live (operations):** workbook connected live to the marts in Postgres / DuckDB. When Prefect updates the marts, the dashboard updates without republishing.
- **Public (showcase for recruiters):** a manual snapshot on Tableau Public. Tableau Public does not allow automated refresh — this repo does not pretend otherwise.

## Sheets to build (from data/marts/*.csv)
1. **Demand vs. capacity** — `mart_demand_daily`: date on columns, demand + completed as lines, capacity as area.
2. **Backlog & SLA** — `mart_backlog_sla`: backlog as line, 5,000 SLA limit as reference line, `sla_ok` as colour. The spike (days 18–22) should be visible.
3. **Capacity & absenteeism** — `mart_capacity_daily`: analysts_available vs. scheduled, utilisation = completed / capacity.
4. **Backlog by queue** — `mart_staffing_scenario`: backlog by queue, filter by queue. Sanctions (2-day SLA) is the tightest.
5. **What-if — 3-month monthly forecast** — from `data/forecast_3m.csv`: ending backlog and total cost by forecast month (M1–M3) for base / overtime 50h/day / hire 30 / both, under the sustained +25% surge. Show the ±1 std interval (`ending_backlog_low` / `ending_backlog_high`) as a band, not just the central line. State the cost assumptions on the sheet (illustrative, not real figures). The headline: do-nothing breaches SLA in M3 (7,936); hire holds it at 231.
6. **Monthly history** — from `data/monthly_history.csv` / `mart_monthly_summary`: demand vs. capacity by month, peak backlog annotated (853 in Jan, spike days 18–22).
7. **Daily ops** — from `data/ops_daily.csv`: utilisation %, absenteeism %, spike days flagged, shortfall. This is the complement to the monthly forecast, not a duplicate of it.
8. **Monte Carlo** — from `data/monte_carlo.json`: P50 / P90 ending backlog by month, P(SLA breach). Under +25% surge, M3 P50 8,070, P90 9,541, breach 100%.
9. **WFM** — from `data/wfm_summary.json`: required FTE gross / net / at 85% utilisation, Little's Law wait, aging estimate, required FTE by queue.

## Publish to Tableau Public (manual, ~10 min)
1. Run `python3 flows/capacity_pipeline.py` to regenerate `data/marts/*.csv`.
2. In Tableau Desktop / Public: connect to the 4 mart CSVs, build the 5 sheets above, publish.
3. Paste the Public URL in the repo README.

## build_hyper.py
Generates a `.hyper` extract from the marts when `tableauhyperapi` is installed. Without it, it prints the manual steps above and exits 0 — it never fakes an extract.
