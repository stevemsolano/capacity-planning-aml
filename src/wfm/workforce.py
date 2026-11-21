"""Modern capacity planning / workforce management concepts, back-office edition.

This is AML/KYC back-office capacity planning — NOT contact-center
Erlang C / Genesys. No Erlang C is claimed here: back-office work is
queued cases with an SLA in days, not calls with a service level in
seconds. The concepts below are the back-office equivalents, each
with a formula, a test, and a documented assumption.

1. Shrinkage: productive time lost to absence, training, PTO, etc.
   shrinkage = absent / scheduled + training (3% illustrative).
   Productive analysts = scheduled * (1 - shrinkage).
2. Required FTE, in three steps so the buffer is visible:
   gross  = demand / productivity
   net    = gross / (1 - shrinkage)
   staffed at target utilisation (85%) = net / 0.85
   Staffing at 100% utilisation is a queuing trap: as utilisation
   approaches 100%, wait time explodes. The 85% target is the buffer
   that buys variability absorption. Change it in one place.
3. Little's Law: WIP = throughput x flow time, so
   avg wait (days) = backlog / completed per day.
   That is how backlog becomes a wait-time story a stakeholder feels.
4. Aging (estimated): with no case-level ages in the synthetic feed,
   backlog is split by the Little's Law wait: 0-2 days, 3-5 days,
   >5 days. Labelled as an estimate, never as case-level truth.
5. Skill mix: required FTE per queue, with queue productivity factors
   (ILLUSTRATIVE, not real figures): KYC 1.00, TM QC 0.90 (slower,
   deeper review), Sanctions 1.15 (faster screening). A single
   blended productivity hides where the shortage really is.
6. Hiring lead time + ramp: a hire decided today is not productive
   today (see simulator RAMP). The forecast already prices that.
"""
import math

TARGET_UTILISATION = 0.85
TRAINING_PCT = 0.03  # illustrative: 3% of scheduled time in training
QUEUE_PRODUCTIVITY_FACTOR = {
    "kyc_onboarding": 1.00,
    "tm_qc": 0.90,
    "sanctions_screening": 1.15,
}


def shrinkage_rate(scheduled, absent, training_pct=TRAINING_PCT):
    """Share of scheduled time not available for cases."""
    if not scheduled:
        return 0.0
    return round(absent / scheduled + training_pct, 4)


def required_fte(demand_per_day, productivity_per_day,
                 shrinkage=0.0, target_utilisation=TARGET_UTILISATION):
    """Return gross / net / staffed FTE for one day's demand."""
    if productivity_per_day <= 0:
        raise ValueError("productivity must be > 0")
    gross = demand_per_day / productivity_per_day
    net = gross / (1 - shrinkage) if shrinkage < 1 else float("inf")
    staffed = net / target_utilisation if target_utilisation else net
    return {
        "gross_fte": round(gross, 1),
        "net_fte_shrinkage": round(net, 1),
        "staffed_fte_at_target_utilisation": round(staffed, 1),
        "shrinkage": shrinkage,
        "target_utilisation": target_utilisation,
    }


def littles_law_wait_days(backlog, completed_per_day):
    """Average wait in queue (days) from Little's Law: W = L / lambda."""
    if completed_per_day <= 0:
        return float("inf") if backlog > 0 else 0.0
    return round(backlog / completed_per_day, 2)


def aging_estimate(backlog, avg_wait_days):
    """Split backlog into age buckets from the Little's Law wait.

    Estimate only: the synthetic feed has no case-level ages.
    Assumes wait is roughly exponential — most cases young, a long
    tail old. When avg wait is low, almost everything is 0-2 days;
    when it is high, the >5-day bucket grows.
    """
    if backlog <= 0:
        return {"age_0_2_days": 0, "age_3_5_days": 0, "age_over_5_days": 0}
    # P(wait <= t) = 1 - exp(-t / mean) for an exponential wait.
    mean = max(avg_wait_days, 0.1)
    p_2 = 1 - math.exp(-2 / mean)
    p_5 = 1 - math.exp(-5 / mean)
    return {
        "age_0_2_days": int(round(backlog * p_2)),
        "age_3_5_days": int(round(backlog * (p_5 - p_2))),
        "age_over_5_days": int(round(backlog * (1 - p_5))),
    }


def required_fte_by_queue(queue_demand_per_day, productivity_per_day,
                          shrinkage=0.0,
                          target_utilisation=TARGET_UTILISATION):
    """Required FTE per queue, using queue productivity factors."""
    out = {}
    for queue, demand in queue_demand_per_day.items():
        factor = QUEUE_PRODUCTIVITY_FACTOR.get(queue, 1.0)
        out[queue] = required_fte(
            demand, productivity_per_day * factor,
            shrinkage=shrinkage, target_utilisation=target_utilisation)
        out[queue]["productivity_factor"] = factor
    return out
