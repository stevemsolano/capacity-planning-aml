"""Simulator: the overtime-vs-hire tradeoff must behave like a manager
expects — overtime helps a spike, a hire helps a sustained level,
doing nothing leaves the backlog where it was.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "simulate"))

from generate.generate import generate
from simulator import simulate, compare


def test_overtime_beats_do_nothing_on_backlog():
    rows = generate(days=30, seed=42)
    base = simulate(rows, horizon_weeks=4, name="base")
    ot = simulate(rows, overtime_hours_per_day=50.0, horizon_weeks=4, name="ot")
    assert ot.ending_backlog <= base.ending_backlog
    assert ot.total_cost > 0


def test_hire_costs_more_than_overtime_over_4_weeks_but_clears_more():
    rows = generate(days=30, seed=42)
    ot = simulate(rows, overtime_hours_per_day=50.0, horizon_weeks=4, name="ot")
    hire = simulate(rows, extra_analysts=30, horizon_weeks=4, name="hire")
    assert hire.total_cost > ot.total_cost  # onboarding + salary
    assert hire.ending_backlog <= ot.ending_backlog


def test_higher_demand_worsens_backlog():
    rows = generate(days=30, seed=42)
    normal = simulate(rows, horizon_weeks=4, name="normal")
    surge = simulate(rows, demand_change_pct=20, horizon_weeks=4, name="surge")
    assert surge.ending_backlog >= normal.ending_backlog


def test_surge_makes_the_choice_matter():
    rows = generate(days=30, seed=42)
    base, ot, hire, both = compare(rows, horizon_weeks=4, demand_change_pct=15)
    assert base.ending_backlog > 0  # sustained +15% builds backlog
    assert ot.ending_backlog < base.ending_backlog
    assert hire.ending_backlog < ot.ending_backlog


def test_compare_returns_four_named_scenarios():
    rows = generate(days=30, seed=42)
    names = [s.name for s in compare(rows, horizon_weeks=4)]
    assert names == ["base_do_nothing", "overtime_50h_per_day",
                     "hire_30_analysts", "hire_30_plus_overtime_50h"]
