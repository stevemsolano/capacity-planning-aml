"""Capacity pipeline v2: generate -> load -> marts -> simulate -> checks.

Prefect is optional: if installed the steps run as a Prefect flow
(retries, logs, schedule); if not, they run as plain functions with
identical logic. That keeps the repo runnable on a bare Python install
and honest about what Prefect adds.

Run: python3 flows/capacity_pipeline.py
Outputs: data/raw/*.csv, data/marts/*.csv, data/scenarios.json,
warehouse/capacity.duckdb (if duckdb installed).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "generate"))
sys.path.insert(0, str(ROOT / "src" / "simulate"))
sys.path.insert(0, str(ROOT / "src" / "load"))
sys.path.insert(0, str(ROOT / "src" / "build_marts"))
sys.path.insert(0, str(ROOT / "src" / "forecast"))
sys.path.insert(0, str(ROOT / "src" / "ops"))
sys.path.insert(0, str(ROOT / "src" / "wfm"))

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover - runs without Prefect
    def flow(fn):
        return fn

    def task(fn):
        return fn

from generate import generate
from simulator import compare
import load_duckdb
import build_marts
import monthly_forecast
import daily_ops
import backtest
import monte_carlo
import workforce


@task
def load_demand():
    # 90 days of daily history (the engine); planning is monthly, 3 months out.
    return generate(days=90, seed=42)


@task
def run_all(rows):
    # 1. Generate CSVs (also writes data/raw/)
    from generate import main as gen_main
    gen_main(["--days", "90", "--seed", "42"])
    # 3b. Monthly 3-month forecast (the planning view)
    hist, forecast = monthly_forecast.write_outputs(rows)
    # 3c. Daily ops (complement, not replaced) + backtest + Monte Carlo
    ops, ops_summary = daily_ops.write_outputs(rows)
    backtest_result = backtest.write_output(rows)
    mc_result = monte_carlo.write_output(rows)
    # 3d. Modern WFM summary: shrinkage, required FTE, Little's Law, aging, skill mix
    last = rows[-1]
    avg_demand = monthly_forecast._avg_weekday(rows, "demand")
    avg_prod = monthly_forecast._avg_weekday(rows, "productivity")
    shrink = workforce.shrinkage_rate(
        last["analysts_scheduled"], last["absent"])
    wfm_summary = {
        "avg_weekday_demand": round(avg_demand, 1),
        "avg_productivity": round(avg_prod, 2),
        "shrinkage_last_day": shrink,
        "required_fte": workforce.required_fte(avg_demand, avg_prod, shrinkage=shrink),
        "littles_law_avg_wait_days_peak": workforce.littles_law_wait_days(
            max(r["backlog"] for r in rows),
            sum(r["completed"] for r in rows) / len(rows)),
        "aging_at_peak_backlog": workforce.aging_estimate(
            max(r["backlog"] for r in rows),
            workforce.littles_law_wait_days(
                max(r["backlog"] for r in rows),
                sum(r["completed"] for r in rows) / len(rows))),
        "required_fte_by_queue": workforce.required_fte_by_queue(
            {"kyc_onboarding": avg_demand * 0.45, "tm_qc": avg_demand * 0.35,
             "sanctions_screening": avg_demand * 0.20},
            avg_prod, shrinkage=shrink),
    }
    (ROOT / "data" / "wfm_summary.json").write_text(
        json.dumps(wfm_summary, indent=2))
    # 2. Load warehouse (DuckDB if installed, else a clear skip)
    load_duckdb.main()
    # 3. Build marts + export CSVs for Tableau
    build_marts.main()
    # 4. Price the decision over 4 weeks (also 8/12 in scenarios.json).
    #    The no-shock base holds SLA from a 0 backlog, so the priced
    #    decision is the sustained +25% demand surge (the historical
    #    spike, made sustained) — that is where overtime vs. hire
    #    actually differs.
    from dataclasses import asdict
    scenarios = {}
    for weeks in (4, 8, 12):
        scenarios[f"{weeks}w"] = [
            asdict(s) for s in compare(rows, horizon_weeks=weeks)
        ]
    scenarios["4w_demand_plus25"] = [
        asdict(s) for s in compare(rows, horizon_weeks=4, demand_change_pct=25)
    ]
    scenarios["12w_demand_plus25"] = [
        asdict(s) for s in compare(rows, horizon_weeks=12, demand_change_pct=25)
    ]
    out = ROOT / "data" / "scenarios.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scenarios, indent=2))
    return scenarios, forecast, ops_summary, backtest_result, mc_result, wfm_summary


@flow
def capacity_pipeline():
    rows = load_demand()
    scenarios, forecast, ops_summary, backtest_result, mc_result, wfm_summary = run_all(rows)
    print(f"{len(rows)} days, final backlog {rows[-1]['backlog']} "
          f"(peak in window: {max(r['backlog'] for r in rows)})")
    print("4w, no shock (base holds from 0 backlog):")
    for s in scenarios["4w"]:
        print(f"  {s['name']}: ending backlog {s['ending_backlog']}, "
              f"cost ${s['total_cost']:,.0f}")
    print("4w, sustained demand +25% (the priced decision):")
    for s in scenarios["4w_demand_plus25"]:
        print(f"  {s['name']}: ending backlog {s['ending_backlog']}, "
              f"SLA breach days {s['sla_breach_days']}, "
              f"cost ${s['total_cost']:,.0f} — {s['recommendation']}")
    print("scenarios written to data/scenarios.json")
    print("3-month monthly forecast (demand +25% surge):")
    for r in forecast:
        if r["demand_shock"] == "demand +25%":
            print(f"  M{r['forecast_month']} {r['scenario']}: "
                  f"ending backlog {r['ending_backlog']} "
                  f"(low {r['ending_backlog_low']} / high {r['ending_backlog_high']}), "
                  f"cost ${r['total_cost']:,.0f}")
    print(f"Daily ops: {ops_summary}")
    print(f"Backtest (train 60d -> next business days): {backtest_result}")
    print(f"Monte Carlo +25% surge, M3: {mc_result['demand_plus25'][2]}")
    print(f"WFM: required FTE {wfm_summary['required_fte']}; "
          f"Little's Law wait at peak "
          f"{wfm_summary['littles_law_avg_wait_days_peak']} days")
    print("forecast written to data/forecast_3m.csv/.json; "
          "history to data/monthly_history.csv; "
          "ops to data/ops_daily.csv; backtest to data/backtest.json; "
          "Monte Carlo to data/monte_carlo.json; WFM to data/wfm_summary.json")
    return scenarios, forecast, ops_summary, backtest_result, mc_result, wfm_summary


if __name__ == "__main__":
    capacity_pipeline()
