"""Daily ops + modern WFM: shrinkage, required FTE, Little's Law,
aging, skill mix, Monte Carlo. Back-office concepts only — no
contact-center Erlang C is claimed anywhere in this repo.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ops"))
sys.path.insert(0, str(ROOT / "src" / "wfm"))
sys.path.insert(0, str(ROOT / "src" / "forecast"))

from generate.generate import generate
from daily_ops import daily_ops, ops_summary
from workforce import (
    shrinkage_rate, required_fte, littles_law_wait_days,
    aging_estimate, required_fte_by_queue, TARGET_UTILISATION,
)
from monte_carlo import monte_carlo


def test_ops_flags_the_spike_days():
    rows = generate(days=90, seed=42)
    ops = daily_ops(rows)
    assert len(ops) == 90
    # Spike period is days 18-22; the 120%-of-average rule flags 2 of
    # them (weekend spike days have lower absolute demand by design).
    assert sum(1 for o in ops if o["spike_day"]) >= 2
    s = ops_summary(ops)
    assert s["peak_backlog"] == 853
    assert s["total_shortfall"] >= 0
    assert 0 <= s["avg_absent_rate_pct"] <= 20


def test_shrinkage_and_required_fte_buffer():
    # 100 cases/day at 5/day = 20 gross FTE; shrinkage + 85% target
    # utilisation must staff MORE than gross, never less.
    r = required_fte(100, 5.0, shrinkage=0.08)
    assert r["gross_fte"] == 20.0
    assert r["net_fte_shrinkage"] > 20.0
    assert r["staffed_fte_at_target_utilisation"] > r["net_fte_shrinkage"]
    assert r["target_utilisation"] == TARGET_UTILISATION
    assert shrinkage_rate(400, 32) > 0.08  # 8% absent + 3% training


def test_littles_law_and_aging_add_up():
    assert littles_law_wait_days(1000, 500) == 2.0
    buckets = aging_estimate(1000, 2.0)
    assert sum(buckets.values()) == 1000
    assert buckets["age_over_5_days"] < buckets["age_0_2_days"]
    # Longer wait -> older backlog.
    assert aging_estimate(1000, 6.0)["age_over_5_days"] > buckets["age_over_5_days"]


def test_skill_mix_tm_needs_more_fte_than_sanctions_for_same_demand():
    by_queue = required_fte_by_queue(
        {"tm_qc": 100, "sanctions_screening": 100}, 5.0, shrinkage=0.0)
    assert (by_queue["tm_qc"]["gross_fte"]
            > by_queue["sanctions_screening"]["gross_fte"])


def test_monte_carlo_p90_above_p50_and_seeded():
    rows = generate(days=90, seed=42)
    mc1 = monte_carlo(rows, demand_change_pct=25, n_runs=50, seed=42)
    mc2 = monte_carlo(rows, demand_change_pct=25, n_runs=50, seed=42)
    assert mc1 == mc2  # seeded = reproducible
    assert len(mc1) == 3
    for m in mc1:
        assert m["ending_backlog_p90"] >= m["ending_backlog_p50"]
        assert 0 <= m["p_sla_breach_pct"] <= 100
