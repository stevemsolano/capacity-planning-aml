# Decision log (ADRs) — why this project looks the way it does

A generic AI dump has no decisions. This repo does. Each ADR records
the context, the decision, the alternative rejected, and the cost of
the choice. If a reviewer asks "why did you do it this way?", the
answer is here — and in the code the ADR points to.

## ADR-1: Synthetic data, seeded — no real employer data
- Context: the domain is AML/KYC capacity planning, learned running a back-office AML/KYC operation at a large bank.
  Real data, names, or screenshots can never go in a public repo.
- Decision: 100% synthetic, fixed seed 42, scale inspired by the real
  operation (~50,000 cases/month, ~400 analysts) without copying it.
- Rejected: anonymised real extracts (still a leak risk, and
  unreproducible), and a generic public dataset (no AML/KYC queues,
  no SLA in days, no staffing decision).
- Cost: the numbers prove the method, not the operation. The README
  and every cost figure say so.

## ADR-2: Monthly planning, daily engine — not daily planning
- Context: hiring takes weeks; a daily forecast hides the decision.
- Decision: 90 days of daily history as the engine; planning is a
  3-month monthly forecast (22 / 22 / 21 business days).
- Rejected: daily-only planning (operational, not staffing) and
  quarterly-only planning (too coarse to catch a spike becoming
  sustained).
- Cost: the monthly view needs a daily engine underneath, so the repo
  carries both. Daily ops is kept as a complement (`src/ops/`).

## ADR-3: Prefect as orchestrator, Airflow as documented variant
- Context: the pipeline needs retries, logs, schedule, observability.
- Decision: Prefect, Python-native, optional (the flow runs as plain
  functions without it). Airflow mapped 1:1 in `docs/orchestration.md`.
- Rejected: maintaining two pipelines in parallel (double the bugs,
  half the tests each), and Autosys as the demo orchestrator (no free
  tier / server / licence, no lineage, no data tests).
- Cost: a reviewer who wants Airflow must read the mapping, not run it.

## ADR-4: dbt is the single definition of each metric
- Context: backlog and SLA were defined in five dashboards in the
  real world. That is how numbers disagree in a meeting.
- Decision: one definition lives in `mart_backlog_sla.sql`
  (backlog < 5,000 = sla_ok). Dashboards read marts, never raw tables.
- Rejected: defining metrics in Tableau / SQL scattered across
  notebooks.
- Cost: changing a definition means editing one model + its tests.

## ADR-5: Target utilisation 85%, not 100%
- Context: staffing at 100% utilisation looks efficient on paper.
- Decision: required FTE is shown gross / net / staffed at 85%.
- Rejected: 100% (queuing trap — as utilisation approaches 100%,
  wait time explodes; there is no slack for a spike or an absence).
- Cost: the staffed number is ~28% above gross FTE (317.6 → 406.5).
  That gap is the point, and it is shown, not hidden.

## ADR-6: Trend is measured, not auto-applied
- Context: OLS on 90 noisy days gives a trend of −4.0%/month.
- Decision: report `trend_monthly_pct`, do not compound it into the
  forecast. A manager sets trend as a judgment input.
- Rejected: auto-applying it (it would have cut the M3 backlog from
  7,936 to ~2,900 on noise alone — the repo proves this in
  `docs/metric-definitions.md`).
- Cost: the forecast is deliberately dumber than a naive OLS
  extrapolation, and more honest for it.

## ADR-7: Scenarios are what-ifs with triggers, not predictions
- Context: a +25% demand forecast presented as a prediction would be
  a lie. It is a scenario: the historical spike, made sustained.
- Decision: every forecast row carries `kind = "scenario — not a
  prediction"`, plus decision triggers (hire when demand runs +25%
  for 2 weeks or backlog crosses 3,000 and is rising).
- Rejected: a single point forecast with no interval, no Monte Carlo,
  and no trigger.
- Cost: the repo must maintain 4 shocks × 4 scenarios × 3 months,
  and explain them, instead of one clean number.

## ADR-8: Forecast accuracy is measured, not asserted
- Context: "my forecast is good" is cheap. A backtest is not.
- Decision: train 60 days → forecast the next business days →
  compare to actuals (MAPE, WAPE, bias). Re-run monthly.
- Rejected: shipping a forecast with no error metric.
- Cost: the current backtest is flattering (MAPE 6.1%, backlog error
  0) because the test window was calm. The file says so by showing
  the test window, not just the score.

## ADR-10: Raw tables land in schema `raw`, not `main`
- Context: the dbt project declared its sources in schema `raw`
  (`{{ source('raw', ...) }}`), but the loader wrote the raw tables
  into DuckDB's default `main` schema. The mismatch was invisible
  until the first real `dbt build` ran in CI and failed with
  "schema raw does not exist" — the pipeline's own DuckDB runner had
  masked it by stripping source references to unqualified names.
- Decision: the loader creates schema `raw` and lands the raw tables
  there; the local runner mirrors dbt's resolution (`raw.<table>`).
  Marts and staging views stay in `main`. One layout, declared in
  one place (`dbt_project/models/schema.yml`), produced by the loader.
- Rejected: pointing the dbt source at schema `main` (one-line fix,
  but it would have blessed a layout where raw feeds sit next to
  marts with nothing separating them).
- Cost: two files changed (loader + runner) instead of one, and the
  fix was verified by the scheduled CI run going green, not by
  assertion.

## ADR-9: No Erlang C, no ML
- Context: this is back-office queueing with an SLA in days, not
  contact-center calls in seconds, and there is no labelled training
  set for a model here.
- Decision: no Erlang C, no Genesys, no ML model. Monte Carlo +
  interval + backtest carry the uncertainty instead.
- Rejected: adding Erlang C to sound "WFM" (wrong domain) and adding
  a gradient-boosting forecaster on 90 synthetic days (overfit
  theatre).
- Cost: a reviewer looking for ML buzzwords will not find them. A
  reviewer looking for judgment will.
