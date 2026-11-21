"""3-month monthly forecast: 3 months, monthly buckets add up,
surge makes the choice matter, hire wins only on a sustained level."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "forecast"))

from generate.generate import generate
from monthly_forecast import (
    aggregate_monthly, forecast_3m, compare_3m, BUSINESS_DAYS_PER_MONTH)


def test_monthly_history_sums_to_daily_totals():
    rows = generate(days=90, seed=42)
    hist = aggregate_monthly(rows)
    assert sum(h["demand"] for h in hist) == sum(r["demand"] for r in rows)
    assert sum(h["days"] for h in hist) == 90
    assert hist[-1]["ending_backlog"] == rows[-1]["backlog"]


def test_forecast_has_3_months_with_65_business_days():
    rows = generate(days=90, seed=42)
    fc = forecast_3m(rows, name="base")
    assert len(fc) == 3
    assert [f["forecast_month"] for f in fc] == [1, 2, 3]
    assert sum(f["business_days"] for f in fc) == 65
    assert BUSINESS_DAYS_PER_MONTH == [22, 22, 21]


def test_surge_hire_beats_overtime_by_month_3():
    rows = generate(days=90, seed=42)
    base = {f["forecast_month"]: f for f in forecast_3m(
        rows, demand_change_pct=25, name="base")}
    hire = {f["forecast_month"]: f for f in forecast_3m(
        rows, extra_analysts=30, demand_change_pct=25, name="hire")}
    ot = {f["forecast_month"]: f for f in forecast_3m(
        rows, overtime_hours_per_day=50.0, demand_change_pct=25, name="ot")}
    assert hire[3]["ending_backlog"] < ot[3]["ending_backlog"]
    assert hire[3]["ending_backlog"] < base[3]["ending_backlog"]
    assert hire[3]["total_cost"] > ot[3]["total_cost"]


def test_compare_3m_returns_4_scenarios_x_3_months():
    rows = generate(days=90, seed=42)
    fc = compare_3m(rows, demand_change_pct=25)
    assert len(fc) == 12
    assert len({r["scenario"] for r in fc}) == 4


def test_forecast_interval_brackets_central_case():
    from monthly_forecast import forecast_3m
    rows = generate(days=90, seed=42)
    for f in forecast_3m(rows, demand_change_pct=25, name="base"):
        assert f["ending_backlog_low"] <= f["ending_backlog"] <= f["ending_backlog_high"]
        assert f["kind"] == "scenario — not a prediction"
        assert -5.0 <= f["trend_monthly_pct"] <= 5.0


def test_attrition_makes_backlog_worse_not_better():
    from monthly_forecast import forecast_3m
    rows = generate(days=90, seed=42)
    no_attr = forecast_3m(rows, demand_change_pct=25, name="x")
    # attrition is a module constant in _run_months; compare via direct run
    from monthly_forecast import _run_months
    with_attr = _run_months(rows, demand_change_pct=25, attrition_monthly_pct=2.0)
    without_attr = _run_months(rows, demand_change_pct=25, attrition_monthly_pct=0.0)
    assert with_attr[2]["ending_backlog"] >= without_attr[2]["ending_backlog"]
