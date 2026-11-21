"""Daily operations view — the complement to the monthly forecast.

Monthly planning does NOT replace daily ops. This module is the daily
lens: shifts, absenteeism, utilisation, and the spike. One row per day,
plus a summary. It reads the same daily rows as the forecast, so the
two views can never disagree about what happened.

Flags (documented in docs/metric-definitions.md):
- spike_day: demand > 120% of the weekday-demand average.
- high_absenteeism: absent / scheduled > 8%.
- over_utilised: completed / capacity > 95% (no slack left that day).
- shortfall: demand - capacity when positive (cases the day could not
  absorb, before backlog).
- sla_risk_day: backlog >= 5,000.
Run: python3 src/ops/daily_ops.py  (also called by the pipeline)
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def daily_ops(rows):
    wd_avg = sum(r["demand"] for r in rows
                 if r.get("weekday") not in ("Sat", "Sun")) / max(
                     1, sum(1 for r in rows
                            if r.get("weekday") not in ("Sat", "Sun")))
    out = []
    for r in rows:
        absent_rate = r["absent"] / r["analysts_scheduled"] if r["analysts_scheduled"] else 0
        utilisation = r["completed"] / r["capacity"] if r["capacity"] else 0
        out.append({
            "day": r["day"],
            "date": r["date"],
            "weekday": r["weekday"],
            "demand": r["demand"],
            "analysts_scheduled": r["analysts_scheduled"],
            "absent": r["absent"],
            "absent_rate_pct": round(absent_rate * 100, 1),
            "analysts_available": r["analysts"],
            "capacity": r["capacity"],
            "completed": r["completed"],
            "utilisation_pct": round(utilisation * 100, 1),
            "backlog": r["backlog"],
            "shortfall": max(0, r["demand"] - r["capacity"]),
            "spike_day": r["demand"] > 1.2 * wd_avg,
            "high_absenteeism": absent_rate > 0.08,
            "over_utilised": utilisation > 0.95,
            "sla_risk_day": r["backlog"] >= 5000,
        })
    return out


def ops_summary(ops):
    n = len(ops)
    return {
        "days": n,
        "spike_days": sum(1 for o in ops if o["spike_day"]),
        "high_absenteeism_days": sum(1 for o in ops if o["high_absenteeism"]),
        "over_utilised_days": sum(1 for o in ops if o["over_utilised"]),
        "sla_risk_days": sum(1 for o in ops if o["sla_risk_day"]),
        "total_shortfall": sum(o["shortfall"] for o in ops),
        "peak_backlog": max(o["backlog"] for o in ops),
        "avg_absent_rate_pct": round(
            sum(o["absent_rate_pct"] for o in ops) / n, 1) if n else 0,
        "avg_utilisation_pct": round(
            sum(o["utilisation_pct"] for o in ops) / n, 1) if n else 0,
    }


def write_outputs(rows):
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    ops = daily_ops(rows)
    with (data_dir / "ops_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ops[0].keys()))
        w.writeheader()
        w.writerows(ops)
    summary = ops_summary(ops)
    (data_dir / "ops_summary.json").write_text(json.dumps(summary, indent=2))
    return ops, summary


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    from generate.generate import generate
    ops, summary = write_outputs(generate(days=90, seed=42))
    print(summary)
