"""Backlog arithmetic: the one definition, tested, not dashboard-checked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generate.generate import generate


def test_backlog_never_negative_and_completed_never_exceeds_available():
    for row in generate(days=30, seed=42):
        assert row["backlog"] >= 0
        assert row["completed"] <= row["capacity"]


def test_same_seed_same_data():
    assert generate(days=10, seed=42) == generate(days=10, seed=42)


def test_sla_flag_matches_threshold():
    for row in generate(days=30, seed=42):
        assert row["sla_ok"] == (row["backlog"] < 5000)
