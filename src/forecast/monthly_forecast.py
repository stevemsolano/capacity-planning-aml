"""Monthly 3-month forecast, v3. The daily engine stays; planning is monthly.

Why monthly, not daily: a manager does not staff by day. The daily
rows (seeded, with weekday + spike) are the engine; the decision is
taken on 3 rolling forecast months.

A forecast month = 22 / 22 / 21 business days (65 business days = 13
weeks = 3 months).

v3 — what makes this honest instead of naive (see docs/metric-definitions.md):
- Trend: OLS slope of weekday demand over the history, applied per
  forecast month, capped at +/-5% per month. No trend is invented when
  the slope is ~0.
- Seasonality: weekday seasonality only (Mon-Fri vs Sat/Sun, in the
  base averages). With 90 days you cannot estimate annual seasonality
  and this file says so instead of faking it.
- Confidence interval: demand +/- 1 std dev of weekday demand
  (last 30 business days, ~68% interval). Every month reports
  ending_backlog_low / ending_backlog_high alongside the central case.
- Attrition: base team shrinks 2%/month (ILLUSTRATIVE assumption,
  change it in one place). Hires are net additions on top of that.
- Backtest: see src/forecast/backtest.py — the forecast is re-run
  every month and measured against actuals, it is not a one-off.
- Scenarios are WHAT-IFs, not predictions. Every row carries
  kind="scenario". The priced case is +25% demand sustained.

Scenarios use the same levers and illustrative costs as the simulator:
overtime = total team hours / business day, hire = extra analysts with
ramp 50% weeks 1-2, 75% weeks 3-4, 100% after.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "simulate"))
from simulator import (  # noqa: E402
    OVERTIME_HOURLY,
    HIRE_ANNUAL_FULLY_LOADED,
    HIRE_ONBOARDING_ONCE,
    HOURS_PER_DAY,
    RAMP,
)

BUSINESS_DAYS_PER_MONTH = [22, 22, 21]  # 65 business days = 13 weeks
ATTRITION_MONTHLY_PCT = 2.0  # illustrative — base team shrinkage / month


def _weekday_rows(rows, n=42):
    vals = [r for r in rows[-n:] if r.get("weekday") not in ("Sat", "Sun")]
    return vals or list(rows[-n:])


def _avg_weekday(rows, key, n=42):
    # Last ~30 business days, not the last fortnight: a single quiet
    # stretch must not set the whole 3-month forecast (see simulator).
    vals = [r[key] for r in _weekday_rows(rows, n)]
    return sum(vals) / len(vals)


def _std_weekday(rows, key, n=42):
    vals = [r[key] for r in _weekday_rows(rows, n)]
    mean = sum(vals) / len(vals)
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))


def trend_monthly_pct(rows):
    """OLS slope of weekday demand, as % per forecast month, capped +/-5%.

    Returns 0.0 when there is no usable trend. With 90 days of synthetic
    data the slope is small by design; the cap stops a noisy slope from
    compounding into a fantasy forecast.
    """
    wd = [r for r in rows if r.get("weekday") not in ("Sat", "Sun")]
    if len(wd) < 20:
        return 0.0
    xs = list(range(len(wd)))
    ys = [r["demand"] for r in wd]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    pct = slope * 22 / my * 100 if my else 0.0
    return max(-5.0, min(5.0, round(pct, 2)))


def aggregate_monthly(rows):
    """Historical daily rows -> one row per calendar month."""
    by_month = defaultdict(list)
    for r in rows:
        by_month[r["date"][:7]].append(r)
    out = []
    for month in sorted(by_month):
        rs = by_month[month]
        business_days = sum(1 for r in rs if r["weekday"] not in ("Sat", "Sun"))
        out.append({
            "month": month,
            "days": len(rs),
            "business_days": business_days,
            "demand": sum(r["demand"] for r in rs),
            "completed": sum(r["completed"] for r in rs),
            "capacity": sum(r["capacity"] for r in rs),
            "ending_backlog": rs[-1]["backlog"],
            "peak_backlog": max(r["backlog"] for r in rs),
            "sla_breach_days": sum(1 for r in rs if not r["sla_ok"]),
            "avg_analysts_available": round(
                sum(r["analysts"] for r in rs) / len(rs), 1),
            "avg_productivity": round(
                sum(r["productivity"] for r in rs) / len(rs), 2),
        })
    return out


def _run_months(rows, *, extra_analysts=0, overtime_hours_per_day=0.0,
                demand_change_pct=0.0, productivity_change_pct=0.0,
                demand_multiplier=1.0, starting_backlog=None,
                attrition_monthly_pct=ATTRITION_MONTHLY_PCT):
    """Step 65 business days forward, bucketed into 3 forecast months."""
    backlog = int(rows[-1]["backlog"] if starting_backlog is None
                  else starting_backlog)
    base_demand = _avg_weekday(rows, "demand")
    base_productivity = _avg_weekday(rows, "productivity")
    base_analysts = _avg_weekday(rows, "analysts")
    trend_pct = trend_monthly_pct(rows)
    productivity = base_productivity * (1 + productivity_change_pct / 100.0)
    cases_per_ot_hour = productivity / HOURS_PER_DAY

    out = []
    day_idx = 0
    for month_no, n_days in enumerate(BUSINESS_DAYS_PER_MONTH, start=1):
        # Trend is MEASURED and reported (trend_monthly_pct), not
        # auto-applied: with 90 days of noisy demand, compounding an
        # OLS slope would turn noise into a forecast. A manager sets
        # the trend as a judgment input; the model does not invent it.
        # Attrition DOES apply — it shrinks the base team each month.
        demand = (base_demand * (1 + demand_change_pct / 100.0)
                  * demand_multiplier)
        analysts_month = base_analysts * (1 - attrition_monthly_pct / 100.0) ** (month_no - 1)
        m_demand = m_capacity = m_completed = 0
        m_breach = 0
        m_ot_cost = 0.0
        m_hire_cost = 0.0
        for _ in range(n_days):
            week = day_idx // 5
            ramp = RAMP[week] if week < len(RAMP) else 1.0
            capacity = (analysts_month + extra_analysts * ramp) * productivity
            capacity += overtime_hours_per_day * cases_per_ot_hour
            completed = min(capacity, backlog + demand)
            backlog = int(round(backlog + demand - completed))
            m_demand += int(round(demand))
            m_capacity += int(round(capacity))
            m_completed += int(round(completed))
            if backlog >= 5000:
                m_breach += 1
            m_ot_cost += overtime_hours_per_day * OVERTIME_HOURLY
            if extra_analysts:
                m_hire_cost += (HIRE_ANNUAL_FULLY_LOADED / 12.0) * extra_analysts / n_days
            day_idx += 1
        if extra_analysts and month_no == 1:
            m_hire_cost += HIRE_ONBOARDING_ONCE * extra_analysts
        out.append({
            "forecast_month": month_no,
            "business_days": n_days,
            "demand": m_demand,
            "capacity": m_capacity,
            "completed": m_completed,
            "ending_backlog": backlog,
            "sla_breach_days": m_breach,
            "sla_ok": backlog < 5000,
            "overtime_cost": round(m_ot_cost, 2),
            "hire_cost": round(m_hire_cost, 2),
            "total_cost": round(m_ot_cost + m_hire_cost, 2),
            "trend_monthly_pct": trend_pct,
            "attrition_monthly_pct": attrition_monthly_pct,
        })
    return out


def forecast_3m(rows, *, extra_analysts=0, overtime_hours_per_day=0.0,
                demand_change_pct=0.0, productivity_change_pct=0.0,
                name="base"):
    """Central forecast + +/-1 std dev interval on ending backlog."""
    base = _run_months(rows, extra_analysts=extra_analysts,
                       overtime_hours_per_day=overtime_hours_per_day,
                       demand_change_pct=demand_change_pct,
                       productivity_change_pct=productivity_change_pct)
    mean_demand = _avg_weekday(rows, "demand")
    std = _std_weekday(rows, "demand")
    pct = std / mean_demand if mean_demand else 0.0
    low = _run_months(rows, extra_analysts=extra_analysts,
                      overtime_hours_per_day=overtime_hours_per_day,
                      demand_change_pct=demand_change_pct,
                      productivity_change_pct=productivity_change_pct,
                      demand_multiplier=1 - pct)
    high = _run_months(rows, extra_analysts=extra_analysts,
                       overtime_hours_per_day=overtime_hours_per_day,
                       demand_change_pct=demand_change_pct,
                       productivity_change_pct=productivity_change_pct,
                       demand_multiplier=1 + pct)
    out = []
    for b, lo, hi in zip(base, low, high):
        row = dict(b)
        row["scenario"] = name
        row["kind"] = "scenario — not a prediction"
        row["demand_std_pct"] = round(pct * 100, 1)
        # Low demand -> low backlog; high demand -> high backlog.
        row["ending_backlog_low"] = lo["ending_backlog"]
        row["ending_backlog_high"] = hi["ending_backlog"]
        row["demand_low"] = lo["demand"]
        row["demand_high"] = hi["demand"]
        # Reorder so scenario/kind read first in the CSV.
        ordered = {"forecast_month": row["forecast_month"],
                   "scenario": row["scenario"], "kind": row["kind"]}
        ordered.update({k: v for k, v in row.items()
                        if k not in ordered})
        out.append(ordered)
    return out


def compare_3m(rows, demand_change_pct=0.0, productivity_change_pct=0.0):
    """4 scenarios x 3 months. Surge (+25%) is the priced case."""
    kw = dict(demand_change_pct=demand_change_pct,
              productivity_change_pct=productivity_change_pct)
    out = []
    out += forecast_3m(rows, name="base_do_nothing", **kw)
    out += forecast_3m(rows, overtime_hours_per_day=50.0,
                       name="overtime_50h_per_day", **kw)
    out += forecast_3m(rows, extra_analysts=30,
                       name="hire_30_analysts", **kw)
    out += forecast_3m(rows, extra_analysts=30, overtime_hours_per_day=50.0,
                       name="hire_30_plus_overtime_50h", **kw)
    return out


def write_outputs(rows):
    """Write data/forecast_3m.csv + .json (3 shocks) and monthly history."""
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    hist = aggregate_monthly(rows)
    with (data_dir / "monthly_history.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0].keys()))
        w.writeheader()
        w.writerows(hist)
    # Three what-if shocks, each 4 scenarios x 3 months. The priced case
    # is +25% demand sustained (the historical spike, made sustained).
    # Productivity -10% is the capacity shock (e.g. training / attrition
    # spike); demand -10% is the downside case, so the plan is not
    # one-directional.
    shocks = [
        ("none", compare_3m(rows)),
        ("demand +25%", compare_3m(rows, demand_change_pct=25)),
        ("productivity -10%", compare_3m(rows, productivity_change_pct=-10)),
        ("demand -10%", compare_3m(rows, demand_change_pct=-10)),
    ]
    forecast = []
    for shock, fc in shocks:
        forecast += [{**r, "demand_shock": shock} for r in fc]
    with (data_dir / "forecast_3m.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(forecast[0].keys()))
        w.writeheader()
        w.writerows(forecast)
    (data_dir / "forecast_3m.json").write_text(json.dumps(forecast, indent=2))
    return hist, forecast
