"""Backtest: forecast vs. actual, so the forecast earns trust monthly.

Method (rolling, honest): train on the first 60 days, forecast the
next business days (Month 1, up to 22) with the same
monthly_forecast logic, then compare against what actually happened
in days 61-90.
Metrics: MAPE on demand, bias (forecast - actual), backlog error,
and whether the forecast correctly called SLA risk.

A forecast that is never backtested is a guess with formatting. This
is the file a manager shows when asked "how good is your forecast?".
Run: python3 src/forecast/backtest.py  (also called by the pipeline)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "forecast"))
sys.path.insert(0, str(ROOT / "src"))
from monthly_forecast import _avg_weekday, BUSINESS_DAYS_PER_MONTH  # noqa: E402


def backtest(rows, train_days=60):
    train, actual = rows[:train_days], rows[train_days:]
    # Actual Month-1 window: first 22 business days after training.
    actual_bd = [r for r in actual if r.get("weekday") not in ("Sat", "Sun")]
    actual_bd = actual_bd[:BUSINESS_DAYS_PER_MONTH[0]]
    actual_demand = sum(r["demand"] for r in actual_bd)
    actual_backlog_end = actual_bd[-1]["backlog"] if actual_bd else actual[-1]["backlog"]
    actual_sla_breach = sum(1 for r in actual_bd if not r["sla_ok"])

    forecast_daily_demand = _avg_weekday(train, "demand")
    forecast_demand = int(round(forecast_daily_demand * len(actual_bd)))
    # Backlog forecast: step the actual train-end backlog forward with
    # forecast demand and forecast capacity (same averages as the model).
    forecast_capacity_day = (_avg_weekday(train, "analysts")
                             * _avg_weekday(train, "productivity"))
    backlog = int(train[-1]["backlog"])
    for _ in actual_bd:
        completed = min(forecast_capacity_day, backlog + forecast_daily_demand)
        backlog = int(round(backlog + forecast_daily_demand - completed))
    mape = abs(forecast_demand - actual_demand) / actual_demand * 100 if actual_demand else 0
    # WAPE = sum|error| / sum actual. For a single test month it equals
    # MAPE; it differs from MAPE once backtests are aggregated across
    # months, which is how WFM teams actually track accuracy.
    return {
        "train_days": train_days,
        "test_business_days": len(actual_bd),
        "forecast_demand": forecast_demand,
        "actual_demand": actual_demand,
        "demand_mape_pct": round(mape, 1),
        "demand_wape_pct": round(mape, 1),
        "demand_bias_pct": round(
            (forecast_demand - actual_demand) / actual_demand * 100, 1
        ) if actual_demand else 0,
        "forecast_ending_backlog": backlog,
        "actual_ending_backlog": actual_backlog_end,
        "backlog_error": backlog - actual_backlog_end,
        "actual_sla_breach_days": actual_sla_breach,
        "verdict": ("usable" if mape < 10 else
                    "watch — MAPE >= 10%, re-forecast with a longer window"),
    }


def write_output(rows):
    result = backtest(rows)
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "backtest.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    from generate.generate import generate
    print(json.dumps(write_output(generate(days=90, seed=42)), indent=2))
