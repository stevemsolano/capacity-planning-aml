"""Backtest: the forecast is measured, not asserted."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "forecast"))

from generate.generate import generate
from backtest import backtest


def test_backtest_returns_mape_wape_bias_and_verdict():
    rows = generate(days=90, seed=42)
    r = backtest(rows)
    assert r["train_days"] == 60
    assert r["test_business_days"] == 21  # 21 business days in days 61-90
    assert r["forecast_demand"] > 0 and r["actual_demand"] > 0
    assert 0 <= r["demand_mape_pct"] <= 100
    assert r["demand_wape_pct"] == r["demand_mape_pct"]  # single test month
    assert r["verdict"] in ("usable", "watch — MAPE >= 10%, re-forecast with a longer window")
