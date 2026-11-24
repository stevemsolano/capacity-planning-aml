# Metric definitions — the single source of truth

Change a definition here (and in the matching dbt model), not in a dashboard.

## Demand & capacity (daily, per queue where noted)
- **demand**: cases arriving that day (synthetic, seeded).
- **analysts_scheduled**: analysts rostered that day.
- **absent**: scheduled analysts out that day (5–9% of scheduled, random with seed).
- **analysts_available** = scheduled − absent. The dashboard never uses scheduled as capacity.
- **productivity**: cases completed per available analyst per day (4.6–5.4, random with seed).
- **capacity** = analysts_available × productivity.
- **completed** = min(capacity, backlog + demand).
- **backlog** = previous backlog + demand − completed. Never negative by construction; tested.

## SLA
- **Aggregate SLA**: backlog < 5,000 = `sla_ok`. At or above 5,000 = SLA at risk.
- **Per queue**: KYC Onboarding 5 days, Transaction Monitoring QC 5 days, Sanctions Screening 2 days. Queue backlog is the aggregate backlog split pro-rata to that queue's share of demand (45% / 35% / 20%). That split is a transparent allocation for the demo, not a claim about real queue backlogs.

## Daily ops vs. monthly planning — two views, one source
- **Daily ops** (`data/ops_daily.csv`, `src/ops/daily_ops.py`): shifts, absenteeism, utilisation, spike. Flags: spike_day = demand > 120% of weekday average; high_absenteeism = absent/scheduled > 8%; over_utilised = completed/capacity > 95%; shortfall = max(0, demand − capacity). Monthly planning complements daily ops; it does not replace it.
- **Monthly planning** (`data/forecast_3m.csv`): staffing, hiring, budget. Same daily rows, aggregated and forecast forward.

## Modern capacity planning / workforce management (back-office)
This is AML/KYC back-office capacity planning — **NOT contact-center Erlang C / Genesys**. Back-office work is queued cases with an SLA in days, not calls with a service level in seconds. No Erlang C is claimed here.
- **Shrinkage** (`src/wfm/workforce.py`): share of scheduled time not available for cases = absent/scheduled + training (3% illustrative). Productive analysts = scheduled × (1 − shrinkage).
- **Required FTE, in three steps** so the buffer is visible: gross = demand / productivity; net = gross / (1 − shrinkage); staffed at target utilisation = net / 0.85. Staffing at 100% utilisation is a queuing trap: as utilisation approaches 100%, wait time explodes. Target utilisation 85% is the buffer.
- **Little's Law**: WIP = throughput × flow time, so avg wait (days) = backlog / completed per day. Backlog becomes wait time in days.
- **Aging (estimated)**: backlog split 0–2 / 3–5 / >5 days from the Little's Law wait (exponential assumption). Estimate only — the synthetic feed has no case-level ages.
- **Skill mix**: required FTE per queue with productivity factors (ILLUSTRATIVE): KYC 1.00, TM QC 0.90 (slower, deeper review), Sanctions 1.15. A single blended productivity hides where the shortage is.
- **Hiring lead time + ramp**: a hire decided today is not productive today — 50% weeks 1–2, 75% weeks 3–4, 100% after. The forecast prices that.

## What-if simulator
- Forecast demand/productivity = last-30-business-day average, adjusted by the what-if %. Simulation runs on business days (5/week). The 30-day window (not 14) is deliberate: a single quiet fortnight must not set the forecast.
- 1 overtime hour = productivity / 8 cases (~0.625 at 5.0/day). The overtime lever is total team hours per business day (50h = ~25 analysts x 2h), not per analyst.
- A hire ramps: 50% productivity weeks 1–2, 75% weeks 3–4, 100% after.

## 3-month monthly forecast (the planning view) — v3
- Daily rows are the engine; planning is monthly. History is aggregated to calendar months in `mart_monthly_summary` / `data/monthly_history.csv` (Apr is partial — 4 days in the 90-day window).
- Forecast months are rolling: Month 1 = next 22 business days, Month 2 = next 22, Month 3 = next 21 (65 business days = 13 weeks = 3 months).
- Forecast demand/capacity use the same last-30-business-day averages as the simulator, stepped day by day inside each month, so ending backlog and SLA breach days are exact.
- **Trend**: OLS slope of weekday demand is MEASURED and reported (`trend_monthly_pct`, capped ±5%), not auto-applied. With 90 days of noisy demand, compounding a slope turns noise into a forecast. A manager sets the trend as a judgment input. Current run measures −4.0%/mo — that is the proof: applying it would have cut the M3 backlog from 7,936 to ~2,900 on noise alone.
- **Seasonality**: weekday seasonality only (Mon–Fri vs Sat/Sun). With 90 days you cannot estimate annual seasonality.
- **Confidence interval**: demand ± 1 std dev of weekday demand (~68% interval). Every month reports `ending_backlog_low` / `ending_backlog_high` alongside the central case.
- **Attrition**: base team shrinks 2%/month (ILLUSTRATIVE). Hires are net additions on top of that.
- **Monte Carlo** (`data/monte_carlo.json`, 200 seeded runs): P50 / P90 ending backlog and P(SLA breach) per month. A point forecast gives one number; Monte Carlo gives the range: in 90% of runs the backlog is at or below Y.
- **Backtest** (`data/backtest.json`, `src/forecast/backtest.py`): train on the first 60 days, forecast the next business days, compare to actuals. Metrics: MAPE, WAPE, bias, backlog error. The forecast is re-run monthly and measured each time. Current run: MAPE 6.1%, bias +6.1% (forecast high), verdict usable.

## Scenarios are what-ifs, not predictions
Every forecast row carries `kind = "scenario — not a prediction"`. Shocks in `data/forecast_3m.csv`: none, demand +25%, productivity −10%, demand −10%.
- Priced case: sustained demand +25% — the historical spike (days 18–22), made sustained.
- **Decision triggers** (the point of a scenario): start the hire process when demand runs +25% above forecast for 2 consecutive weeks OR backlog crosses 3,000 and is rising; use overtime only as a bridge while hiring ramps; re-forecast monthly and retire a scenario when its trigger has not fired for a full month. The point of a scenario is to have the decision ready before demand moves.

## Costs — ILLUSTRATIVE ONLY, not real figures
- Base rate $30/hr, overtime $45/hr (1.5×).
- Hire: $72,000/year fully loaded + $5,000 one-time onboarding.
- These are demo assumptions so the tradeoff is priced and comparable. Change them in `src/simulate/simulator.py` and every scenario reprices.

## What is NOT in this repo
- No real employer data, names, or screenshots. No invented savings figures.
- No Erlang C, no Genesys, no contact-center service level in seconds. This is back-office queueing with an SLA in days.
