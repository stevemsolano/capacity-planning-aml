"""What-if staffing simulator: overtime vs. hiring.

Pure functions, no I/O. All money figures are ILLUSTRATIVE assumptions
for this synthetic demo — labelled as such in docs/metric-definitions.md.
They are NOT real figures. Change them in one place (COSTS below) and
every scenario reprices.

Definitions (see docs/metric-definitions.md):
- productivity is cases / analyst / day. A working day is 8h, so
  cases per overtime hour = productivity / 8 (~0.575 at 4.6/day).
- A hire ramps: 50% productivity weeks 1-2, 75% weeks 3-4, 100% after.
- Overtime clears a spike. A hire clears a sustained level. The
  simulator prices both over the same horizon so the tradeoff is
  comparable.
"""
from dataclasses import dataclass

# --- Illustrative cost assumptions (demo only, not real figures) ---
BASE_HOURLY = 30.0        # $/hour, fully-loaded base rate (illustrative)
OVERTIME_HOURLY = 45.0    # 1.5x base (illustrative)
HIRE_ANNUAL_FULLY_LOADED = 72_000.0  # $/year (illustrative)
HIRE_ONBOARDING_ONCE = 5_000.0      # $ one-time (illustrative)
HOURS_PER_DAY = 8
RAMP = (0.50, 0.50, 0.75, 0.75)  # productivity factor, weeks 1-4


@dataclass
class ScenarioResult:
    name: str
    horizon_weeks: int
    ending_backlog: int
    sla_breach_days: int
    total_cost: float
    overtime_cost: float
    hire_cost: float
    cases_completed: int
    recommendation: str


def _avg_daily(rows, key, n=14):
    vals = [r[key] for r in rows[-n:]]
    return sum(vals) / len(vals) if vals else 0.0


def _avg_weekday(rows, key, n=42):
    """Average over business days only (Mon-Fri), last ~30 business days.

    Staffing is a weekday decision; averaging in Sat/Sun would understate
    both weekday demand and weekday capacity and hide the tradeoff.
    42 calendar days (~30 business days) is used instead of 14 so a
    single quiet fortnight does not set the whole forecast.
    """
    vals = [r[key] for r in rows[-n:] if r.get("weekday") not in ("Sat", "Sun")]
    if not vals:  # fallback if rows carry no weekday field
        return _avg_daily(rows, key, n)
    return sum(vals) / len(vals)


def simulate(rows, *, extra_analysts=0, overtime_hours_per_day=0.0,
             demand_change_pct=0.0, productivity_change_pct=0.0,
             horizon_weeks=4, name="base"):
    """Simulate forward from the last observed backlog.

    rows: daily rows from generate() (needs backlog, demand,
    productivity, analysts). Demand/productivity forecasts use the
    last-14-day average, adjusted by the what-if percentages.
    """
    if not rows:
        raise ValueError("simulate() needs at least one daily row")
    backlog = int(rows[-1]["backlog"])
    # Weekday averages: the staffing decision is Mon-Fri.
    base_demand = _avg_weekday(rows, "demand")
    base_productivity = _avg_weekday(rows, "productivity")
    base_analysts = _avg_weekday(rows, "analysts")

    demand = base_demand * (1 + demand_change_pct / 100.0)
    productivity = base_productivity * (1 + productivity_change_pct / 100.0)
    cases_per_ot_hour = productivity / HOURS_PER_DAY

    # overtime_hours_per_day is TOTAL team overtime hours per business day
    # (e.g. 50h = ~25 analysts x 2h), not per analyst.
    days = horizon_weeks * 5
    sla_breach = 0
    completed_total = 0
    overtime_cost = 0.0
    hire_cost = 0.0

    for day_idx in range(days):
        week = day_idx // 7
        # Hire ramp only applies to the extra analysts.
        ramp = RAMP[week] if week < len(RAMP) else 1.0
        effective_analysts = base_analysts + extra_analysts * ramp
        capacity = effective_analysts * productivity
        capacity += overtime_hours_per_day * cases_per_ot_hour
        completed = min(capacity, backlog + demand)
        backlog = int(round(backlog + demand - completed))
        completed_total += int(round(completed))
        if backlog >= 5000:
            sla_breach += 1
        overtime_cost += overtime_hours_per_day * OVERTIME_HOURLY
        if extra_analysts:
            # Weekly salary spread over 5 business days.
            hire_cost += (HIRE_ANNUAL_FULLY_LOADED / 52.0) * extra_analysts / 5.0

    if extra_analysts:
        hire_cost += HIRE_ONBOARDING_ONCE * extra_analysts

    total = overtime_cost + hire_cost
    if ending_backlog_ok := backlog < 5000:
        rec = "SLA holds"
    else:
        rec = "SLA at risk — backlog still above 5,000"
    if extra_analysts and overtime_hours_per_day:
        rec += "; combined lever"
    elif extra_analysts:
        rec += "; hire covers a sustained level, not a one-week spike"
    elif overtime_hours_per_day:
        rec += "; overtime covers a spike, not a sustained level"

    return ScenarioResult(
        name=name,
        horizon_weeks=horizon_weeks,
        ending_backlog=backlog,
        sla_breach_days=sla_breach,
        total_cost=round(total, 2),
        overtime_cost=round(overtime_cost, 2),
        hire_cost=round(hire_cost, 2),
        cases_completed=completed_total,
        recommendation=rec,
    )


def compare(rows, horizon_weeks=4, demand_change_pct=0.0):
    """The scenarios a manager actually chooses between.

    Overtime lever = 50 total team hours / business day (~25 analysts x 2h).
    Hire lever = 30 analysts. At 4 weeks the hire looks expensive because
    onboarding ($5k x 30) is one-time; at 12 weeks its cost per case wins.
    That is the tradeoff, priced — not a slogan.

    Pass demand_change_pct=15 for the sustained-surge case: with the
    current backlog at 0, the no-shock base holds SLA and the levers
    look free — the surge is what makes the choice matter.
    """
    kw = dict(horizon_weeks=horizon_weeks, demand_change_pct=demand_change_pct)
    return [
        simulate(rows, name="base_do_nothing", **kw),
        simulate(rows, overtime_hours_per_day=50.0,
                 name="overtime_50h_per_day", **kw),
        simulate(rows, extra_analysts=30,
                 name="hire_30_analysts", **kw),
        simulate(rows, extra_analysts=30, overtime_hours_per_day=50.0,
                 name="hire_30_plus_overtime_50h", **kw),
    ]
