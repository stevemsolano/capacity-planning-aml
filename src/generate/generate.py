"""Synthetic AML/KYC demand + capacity generator. v2.

Fixed seed = same data on any machine. No real employer data, names or
screenshots. Scale is *inspired* by the real operation (~50,000
cases/month, ~400 analysts) without copying it.

What v2 adds over the skeleton:
- calendar dates (starts Mon 2026-01-05), weekday effect
- 3 queues with different demand shares and SLA thresholds
- scheduled analysts, absenteeism, available analysts (explicit)
- a demand spike in days 18-22 so backlog actually builds and the
  overtime-vs-hire decision matters

Run: python3 src/generate/generate.py --days 30 --seed 42
Outputs: data/raw/demand_daily.csv and data/raw/demand_by_queue.csv
"""
import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

START_DATE = date(2026, 1, 5)  # a Monday
SLA_BACKLOG_LIMIT = 5000  # aggregate backlog above this = SLA at risk

# queue -> (share of daily demand, SLA in business days for that queue)
QUEUES = {
    "kyc_onboarding": (0.45, 5),
    "tm_qc": (0.35, 5),
    "sanctions_screening": (0.20, 2),
}


def _weekday_factor(d: date) -> float:
    # Mon-Fri full demand, Sat 55%, Sun 40%. Capacity follows the same
    # pattern via scheduled analysts (see below).
    return {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.55, 6: 0.40}[d.weekday()]


def generate(days: int = 30, seed: int = 42):
    """Daily aggregate rows. Backwards-compatible keys kept."""
    rng = random.Random(seed)
    rows = []
    backlog = 0
    for day in range(1, days + 1):
        d = START_DATE + timedelta(days=day - 1)
        wf = _weekday_factor(d)
        # Demand spike days 18-22 (+25%) — a sustained surge, not noise.
        spike = 1.25 if 18 <= day <= 22 else 1.0
        base_demand = rng.randint(1400, 1900)
        demand = int(round(base_demand * wf * spike))
        scheduled = int(round(410 * wf)) + rng.randint(-10, 10)
        scheduled = max(scheduled, 0)
        absent = int(round(scheduled * rng.uniform(0.05, 0.09)))
        analysts = max(scheduled - absent, 0)  # available analysts
        productivity = round(rng.uniform(4.6, 5.4), 2)  # cases/analyst/day
        capacity = int(analysts * productivity)
        completed = min(capacity, backlog + demand)
        backlog = backlog + demand - completed
        rows.append(
            {
                "day": day,
                "date": d.isoformat(),
                "weekday": d.strftime("%a"),
                "demand": demand,
                "analysts_scheduled": scheduled,
                "absent": absent,
                "analysts": analysts,
                "productivity": productivity,
                "capacity": capacity,
                "completed": completed,
                "backlog": backlog,
                "sla_ok": backlog < SLA_BACKLOG_LIMIT,
            }
        )
    return rows


def generate_by_queue(days: int = 30, seed: int = 42):
    """Per-queue demand split. Backlog is split pro-rata to demand.

    This is a transparent allocation, documented in
    docs/metric-definitions.md — not a claim about real queue backlogs.
    """
    daily = generate(days=days, seed=seed)
    rows = []
    for r in daily:
        for queue, (share, sla_days) in QUEUES.items():
            q_demand = int(round(r["demand"] * share))
            q_backlog = int(round(r["backlog"] * share))
            rows.append(
                {
                    "day": r["day"],
                    "date": r["date"],
                    "queue": queue,
                    "sla_days": sla_days,
                    "demand": q_demand,
                    "backlog": q_backlog,
                    "sla_ok": q_backlog < SLA_BACKLOG_LIMIT * share,
                }
            )
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    rows = generate(args.days, args.seed)
    with (raw / "demand_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    qrows = generate_by_queue(args.days, args.seed)
    with (raw / "demand_by_queue.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys()))
        w.writeheader()
        w.writerows(qrows)

    print(f"wrote {len(rows)} daily rows + {len(qrows)} queue rows to {raw} "
          f"(final backlog {rows[-1]['backlog']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
