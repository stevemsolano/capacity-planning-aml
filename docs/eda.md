# EDA — what the numbers actually look like

Small exploratory analysis of the 90-day synthetic history
(`data/raw/demand_daily.csv`, `data/raw/demand_by_queue.csv`, seed 42).
Everything below is computed from those files, not asserted.

## The shape of the data

| Variable | Mean | Median | Std | Min | Max |
|---|---|---|---|---|---|
| Demand / day | 1,417 | 1,536 | 415 | 560 | 2,186 |
| Capacity / day | 1,629 | 1,826 | 454 | 671 | 2,090 |
| Completed / day | 1,417 | 1,536 | 422 | 560 | 2,068 |
| Productivity (cases/analyst/day) | 5.0 | 5.0 | 0.2 | 4.6 | 5.4 |
| Analysts available / day | 326 | 377 | 91 | 142 | 398 |
| Absent / day | 24 | 25 | 8 | 8 | 37 |
| Backlog | 53 | 0 | 170 | 0 | 853 |

Read it carefully: the overall means mix weekdays and weekends, so they
understate the working week. Weekday demand averages ~1,650/day; the
forecast correctly uses weekday averages only (base 1,575/day on the
last 30 business days).

## Weekday effect — the biggest pattern in the data

![Demand by weekday](images/eda-weekday.png)

- Mon–Fri: 1,631 / 1,642 / 1,660 / 1,693 / 1,632 (flat across the week)
- Sat: 950, Sun: 655 — weekends run at ~50% of weekdays

There is no Monday spike and no Friday dip. The weekday effect is
weekday-vs-weekend only, which is why the forecast uses weekday
averages and not a 7-day average.

## Demand distribution (weekdays)

![Weekday demand distribution](images/eda-dist.png)

Roughly symmetric around the mean, no fat tail, no second mode. The
risk in this operation does not come from a wild demand distribution —
it comes from utilisation running at 87%, close to the edge, so a
normal-sized move swings the backlog a lot.

## The spike

- Spike days 18–22 (weekdays): mean demand 2,076 vs 1,631 on other
  weekdays — **+27.3%**, matching the designed +25% spike.
- Backlog peaked at 853 and cleared in about a week.
- Only 17 of 90 days had any backlog at all; 5 days above 500.
  Backlog is zero-inflated: median 0, mean 53.

## Queues

- KYC Onboarding 45.0% (SLA 5 days), Transaction Monitoring QC 35.0%
  (SLA 5 days), Sanctions Screening 20.0% (SLA 2 days).
- The split is exact by design. Sanctions is the tightest SLA with the
  smallest share — the queue to watch first if backlog ever builds.

## Correlations (daily, Pearson) — and what not to conclude

| Pair | r |
|---|---|
| Demand vs completed | 0.99 |
| Analysts vs completed | 0.94 |
| Absent vs completed | 0.78 |
| Demand vs backlog | 0.15 |
| Productivity vs completed | −0.14 |
| Absent vs backlog | −0.02 |

- Demand vs completed 0.99 is trivial: when there is no backlog,
  completed ≈ demand by construction. It proves nothing about
  causality.
- Absent vs completed 0.78 is mostly a weekend artifact: weekends have
  fewer analysts scheduled and less demand. Do not read it as
  "absences drive completions".
- Demand vs backlog 0.15 is the interesting one: daily demand alone
  barely explains backlog. Backlog is driven by the *sustained* gap
  between demand and capacity (the spike window), not by any single
  day's demand. That is why the forecast is monthly and scenario-based,
  not a daily regression.
- SLA held on 90/90 days in history. The breach only appears in the
  forecast under a sustained surge — which is the whole point of the
  project.

## Honest weaknesses the EDA exposes

1. **Productivity barely varies** (std 0.2 on a mean of 5.0). The
   −10% productivity shock in the forecast is an assumption, not an
   observed regime. With real data, productivity by queue and tenure
   would be the first thing to calibrate.
2. **Backlog is mostly zero**, so any correlation with backlog is
   estimated on 17 days. The Monte Carlo and the interval carry the
   uncertainty for exactly this reason.
3. **No annual seasonality** can be estimated from 90 days. The
   weekday pattern is real; anything about Q4 vs Q1 would be invented.
