# Capacity Planning AML/KYC — Project 1

**Decision this answers:** how many analysts do we need next week/month, what happens to backlog and SLA if demand or productivity moves, and what does it cost to cover it with overtime vs. hiring?

**User:** an operations leader running an AML/KYC queue. **Manager signal:** a what-if simulator with costs and trade-offs — not a dashboard of what happened.

**Data:** 100% synthetic, fixed seed (42). No real employer data, names, or screenshots. Scale is inspired by a real back-office AML/KYC operation (~50,000 cases/month, ~400 analysts) without copying it.

**Live dashboard:** https://public.tableau.com/views/capacity-planning-aml/Dashboard1 (Tableau Public, manual snapshot — no auto-refresh)

**Try it live — no install, no clone:** [Interactive tool](https://stevemsolano.github.io/capacity-planning-aml/tool.html) — the full planning tool. Move the sliders (demand, productivity, attrition, trend, hires, overtime) and the forecast recomputes live with the same engine as `src/forecast/monthly_forecast.py`, plus one-way sensitivity analysis (tornado chart), a cost-vs-backlog trade-off chart, and the orchestration flow. Verified against the pipeline: default case reproduces 1,870 / 4,576 / 7,936 exactly. Also live: [simulator (48 real scenarios)](https://stevemsolano.github.io/capacity-planning-aml/simulator-en.html) and [EDA](https://stevemsolano.github.io/capacity-planning-aml/eda.md).

**EDA — what the numbers look like:** `docs/eda.md` — record grain, columns and queues, data-quality checks, weekday effect, demand distribution, spike, per-queue time series, outlier days, correlations, and the honest weaknesses the EDA exposes (productivity barely varies, backlog mostly zero, no annual seasonality). Start here before the forecast.

## The operation being simulated

A back-office AML/KYC case-review operation at a large bank — not a call center. Analysts do not take calls; they work cases: onboarding files to verify, transaction-monitoring alerts to quality-check, sanctions-screening hits to clear. Each case sits in a queue until an analyst picks it up, and the clock that matters is measured in days, not seconds.

**The three queues.** Work arrives in three streams, each with its own service level:

| Queue | Share of demand | SLA (days to clear) | What the work is |
|---|---|---|---|
| KYC Onboarding | 45% | 5 | Verifying new-customer files before the account can operate |
| Transaction Monitoring QC | 35% | 5 | Quality-checking alerts raised by the transaction-monitoring system |
| Sanctions Screening | 20% | 2 | Clearing name matches against sanctions lists — the tightest clock, because a held payment is a held customer |

**Scale and rhythm.** About 400 analysts clear roughly 50,000 cases a month. Demand is weekday-shaped: ~1,650 cases on a typical weekday, ~950 on Saturday, ~655 on Sunday — so the operation staffs ~410 analysts on weekdays and ~150 on weekends. Absenteeism runs 5–9% (mean 6.8%), and an analyst clears about 5 cases a day (4.6–5.4). Utilisation averages 87%, against an 85% target — the team runs close to full, which is why small demand moves swing the backlog.

**How backlog happens.** When demand outruns capacity, cases wait. Backlog is simply cases waiting past today: it was 0 at the end of the 90-day window, peaked at 853 during the demand spike (days 18–22, +25%), and took about a week to clear. SLA holds while aggregate backlog stays under 5,000. The risk is not a single bad day — it is a sustained surge, because hiring takes weeks to ramp (50% productive in weeks 1–2, 75% in weeks 3–4) while overtime only buys hours. That is the planning problem this repo prices: what to do, and when, before the backlog crosses the line.

**What is real and what is not.** The shape of the operation — queues, SLAs, scale, weekday pattern, absenteeism, ramp — is modeled on a real-scale back-office AML/KYC operation. The data itself is 100% synthetic (fixed seed 42), and the money figures are illustrative demo assumptions, not real costs. Nothing here is real employer data.

## Run it in 5 commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 src/generate/generate.py --days 90 --seed 42
python3 flows/capacity_pipeline.py
python3 -m pytest tests/ -q
```

Planning is monthly, not daily: 90 days of daily history are the engine, the decision is a 3-month monthly forecast (Month 1–3 = 22 / 22 / 21 business days). See `data/forecast_3m.csv`.

Without the venv / DuckDB, the pipeline still runs: DuckDB is optional, the simulator and marts fall back to stdlib. With DuckDB installed you also get `warehouse/capacity.duckdb`.

## What you get

| Output | Where | What it proves |
|---|---|---|
| Daily + per-queue demand (90 days) | `data/raw/demand_daily.csv`, `demand_by_queue.csv` | Seeded, reproducible, weekday + spike (days 18–22, +25%) |
| Warehouse | `warehouse/capacity.duckdb` | Raw tables, DuckDB (Postgres via dbt profile) |
| Marts | `data/marts/mart_*.csv` + `dbt_project/models/marts/` | One definition per metric; Tableau reads these CSVs. Includes `mart_monthly_summary` (planning grain) |
| Monthly history | `data/monthly_history.csv` | Demand / capacity / backlog by calendar month (Jan–Mar + partial Apr) |
| 3-month forecast | `data/forecast_3m.csv` + `.json` | 4 scenarios × 3 months × 4 shocks, with ±1 std interval, trend reported, attrition 2%/mo |
| Daily ops | `data/ops_daily.csv` + `ops_summary.json` | Spike / absenteeism / utilisation / shortfall per day — the complement to monthly planning |
| Backtest | `data/backtest.json` | Train 60d → forecast next business days vs. actuals: MAPE, WAPE, bias |
| Monte Carlo | `data/monte_carlo.json` | 200 seeded runs: P50 / P90 backlog and P(SLA breach) per month |
| WFM summary | `data/wfm_summary.json` | Shrinkage, required FTE (gross / net / at 85% utilisation), Little's Law wait, aging, skill mix |
| Scenarios (weekly, reference) | `data/scenarios.json` | Base vs. overtime vs. hire vs. both, over 4 / 8 / 12 weeks |
| Dashboard | `tableau/` | Workbook + spec for Tableau Public (manual publish, see below) |

## The decision, priced — 3-month monthly forecast (verified run, seed 42, 90 days)

Historical window (90 days): final backlog 0, peak backlog 853 during the demand spike (days 18–22, +25%). The spike builds backlog, the team clears it in about a week — that is the story the dashboard shows. Monthly history: Jan demand 40,751, Feb 39,050, Mar 42,081.

Priced decision — sustained demand +25% (the spike, made sustained; in `data/forecast_3m.csv`):

| Scenario | Month 1 backlog | Month 2 backlog | Month 3 backlog | Cost M1 / M2 / M3 |
|---|---|---|---|---|
| Do nothing | 1,870 | 4,576 | **7,936 — SLA breached** | $0 |
| Overtime 50h/day | 1,188 | 3,212 | 5,921 — SLA breached | $49,500 / $49,500 / $47,250 |
| Hire 30 analysts | 0 | 0 | 231 | $330,000* / $180,000 / $180,000 |
| Hire 30 + overtime | 0 | 0 | 0 | $379,500 / $229,500 / $227,250 |

\* Month 1 hire cost includes one-time onboarding ($5,000 × 30). Attrition (2%/mo) is in these numbers: it is why do-nothing worsens from M2 to M3 and why even the hire ends at 231 in M3. Overtime slows the backlog but never stops it; the hire is the only single lever that holds SLA over 3 months. That is the tradeoff, priced: overtime buys time, a hire buys a sustained level. Costs are illustrative demo assumptions, not real figures — see `docs/metric-definitions.md`.

**Uncertainty, not a point:** M3 do-nothing central case is 7,936, with a ±1 std interval of 0 to 18,856. Monte Carlo (200 runs, +25% surge): M3 P50 8,070, P90 9,541, P(SLA breach) 100% — under a sustained +25% surge, breaching SLA by M3 is essentially certain if nothing is done. The interval is wide because utilisation runs at ~87% — near capacity, small demand moves swing backlog a lot. That is the honest story, and it is why the plan is a rolling monthly forecast, not a one-off prediction.

**Decision triggers:** start hiring when demand runs +25% above forecast for 2 consecutive weeks OR backlog crosses 3,000 and is rising. Use overtime only as a bridge while hiring ramps. Re-forecast monthly; retire a scenario when its trigger has not fired for a full month.

## Modern WFM, in one paragraph

Back-office capacity planning, not contact-center Erlang C (none is claimed here). Shrinkage = absent + 3% training; required FTE is shown gross / net / staffed at 85% target utilisation (317.6 / 345.5 / 406.5 FTE for the current weekday demand — the 85% buffer is what absorbs variability). Little's Law turns backlog into wait time (0.6 days at peak backlog 853). Aging is estimated from that wait. Skill mix prices KYC / TM QC / Sanctions separately instead of hiding them in one blended productivity. Forecast accuracy is measured, not asserted: backtest MAPE 6.1%, bias +6.1% (forecast high), verdict usable.

## Stack — and why

- **Prefect (optional):** `flows/capacity_pipeline.py` — generate → load → marts → simulate. Retries and logs when Prefect is installed; runs as plain functions without it.
- **dbt:** `dbt_project/` — staging → intermediate → marts, with tests in `models/schema.yml`. One definition of backlog/SLA lives in `mart_backlog_sla.sql`. A real `dbt build` (8 models, 13 tests) runs green in the scheduled workflow — see the [Actions runs](https://github.com/stevemsolano/capacity-planning-aml/actions/workflows/scheduled.yml).
- **GitHub Actions:** `.github/workflows/ci.yml` — pytest + pipeline on every PR. A failing test blocks the merge. `.github/workflows/scheduled.yml` — the same pipeline plus `dbt build`, daily at 11:00 UTC (06:00 EST) and on manual dispatch, with public run logs.
- **Tableau:** live to the marts in production; Tableau Public is a manual snapshot (see `tableau/README.md`). No fake auto-refresh is claimed.
- **Airflow / Autosys:** Airflow is documented as a 1:1 variant in `docs/orchestration.md`, not a second pipeline. Autosys is the enterprise scheduling layer in banking — it cannot be demoed in a public repo (no free tier / server / licence), so it is mentioned, not faked.

## Metric definitions

`docs/metric-definitions.md` — backlog, SLA (backlog < 5,000), utilisation, queue SLA days, and the simulator's cost assumptions. **All money figures are illustrative demo assumptions, not real figures.**

## Decisions — why it looks this way

`docs/decisions.md` — 10 ADRs, each with the alternative rejected and what it cost. This is the file to read before an interview: if a reviewer asks "why Prefect, why monthly, why no ML, why no Erlang C?", the answer is there, in writing, before they ask.

## What is NOT here

- No real employer data. No invented savings figures.
- No `.twbx` binary as the only artefact: the `.twb` is versioned XML and the marts are CSVs anyone can open.
- No Erlang C, no Genesys, no contact-center service level in seconds. This is back-office queueing with an SLA in days.
- No trend auto-applied from 90 noisy days, no annual seasonality faked from 90 days. Both are reported as limitations, not hidden.
