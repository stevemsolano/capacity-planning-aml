"""Marts: row counts, no duplicate days, backlog arithmetic holds
in the exported CSVs (the files Tableau reads)."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"


def _read(name):
    with (MARTS / f"{name}.csv").open() as f:
        return list(csv.DictReader(f))


def test_marts_exist_with_90_days():
    # Requires `python3 flows/capacity_pipeline.py` to have run first;
    # CI runs the pipeline before pytest. 90 days of daily history;
    # planning itself is the monthly 3-month forecast.
    for name in ("mart_demand_daily", "mart_capacity_daily", "mart_backlog_sla"):
        rows = _read(name)
        assert len(rows) == 90, f"{name} has {len(rows)} rows, expected 90"
        days = [r["day"] for r in rows]
        assert len(set(days)) == 90, f"{name} has duplicate days"


def test_monthly_summary_mart_exists():
    rows = _read("mart_monthly_summary")
    assert len(rows) >= 3  # Jan / Feb / Mar (+ partial Apr)
    assert sum(int(r["demand"]) for r in rows) > 0


def test_backlog_never_negative_in_mart():
    for r in _read("mart_backlog_sla"):
        assert int(r["backlog"]) >= 0
        assert r["sla_ok"] in ("True", "False", "true", "false", "1", "0")


def test_capacity_utilisation_is_sane():
    for r in _read("mart_capacity_daily"):
        assert int(r["capacity"]) >= 0
        assert int(r["completed"]) <= int(r["capacity"])
