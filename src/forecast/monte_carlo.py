"""Monte Carlo forecast: a distribution, not a point.

Run the 3-month forecast 200 times with daily demand sampled from
Normal(mean = weekday average, std = weekday std dev, seed fixed).
Report per month: P50 / P90 ending backlog and P(SLA breach).
A point forecast says "backlog will be 3,740". Monte Carlo says
"in 90% of worlds it is at or below X, and SLA breaches in Y% of
worlds" — that is the version a manager can actually staff against.

Seeded, so the same run gives the same percentiles on any machine.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "forecast"))
sys.path.insert(0, str(ROOT / "src" / "simulate"))
from monthly_forecast import (  # noqa: E402
    _avg_weekday, _std_weekday, BUSINESS_DAYS_PER_MONTH,
    ATTRITION_MONTHLY_PCT,
)
from simulator import HOURS_PER_DAY, RAMP  # noqa: E402


def _percentile(sorted_vals, pct):
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(pct / 100 * len(sorted_vals)))
    return sorted_vals[idx]


def monte_carlo(rows, *, n_runs=200, seed=42, extra_analysts=0,
                overtime_hours_per_day=0.0, demand_change_pct=0.0):
    """200 seeded runs, base scenario unless levers are passed."""
    rng = random.Random(seed)
    mean_demand = _avg_weekday(rows, "demand") * (1 + demand_change_pct / 100.0)
    std_demand = _std_weekday(rows, "demand")
    productivity = _avg_weekday(rows, "productivity")
    base_analysts = _avg_weekday(rows, "analysts")
    # No auto-trend, same rule as the central forecast: the measured
    # trend is reported in the forecast, not compounded into it.
    cases_per_ot_hour = productivity / HOURS_PER_DAY

    per_month_backlogs = {1: [], 2: [], 3: []}
    per_month_breach = {1: 0, 2: 0, 3: 0}
    for _ in range(n_runs):
        backlog = int(rows[-1]["backlog"])
        day_idx = 0
        for month_no, n_days in enumerate(BUSINESS_DAYS_PER_MONTH, start=1):
            demand_base = mean_demand
            analysts_month = base_analysts * (1 - ATTRITION_MONTHLY_PCT / 100.0) ** (month_no - 1)
            for _ in range(n_days):
                demand = max(0, rng.gauss(demand_base, std_demand))
                week = day_idx // 5
                ramp = RAMP[week] if week < len(RAMP) else 1.0
                capacity = (analysts_month + extra_analysts * ramp) * productivity
                capacity += overtime_hours_per_day * cases_per_ot_hour
                completed = min(capacity, backlog + demand)
                backlog = int(round(backlog + demand - completed))
                day_idx += 1
            per_month_backlogs[month_no].append(backlog)
            if backlog >= 5000:
                per_month_breach[month_no] += 1
    out = []
    for month_no in (1, 2, 3):
        vals = sorted(per_month_backlogs[month_no])
        out.append({
            "forecast_month": month_no,
            "runs": n_runs,
            "ending_backlog_p50": _percentile(vals, 50),
            "ending_backlog_p90": _percentile(vals, 90),
            "p_sla_breach_pct": round(per_month_breach[month_no] / n_runs * 100, 1),
        })
    return out


def write_output(rows):
    """Monte Carlo for the two cases that matter: base and +25% surge."""
    result = {
        "base": monte_carlo(rows),
        "demand_plus25": monte_carlo(rows, demand_change_pct=25),
        "demand_plus25_hire30": monte_carlo(
            rows, demand_change_pct=25, extra_analysts=30),
    }
    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "monte_carlo.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    from generate.generate import generate
    print(json.dumps(write_output(generate(days=90, seed=42)), indent=2))
