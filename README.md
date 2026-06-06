# Altis Groep — Weather-Aware 13-Week Cash-Flow Forecast

A working prototype that consolidates **four** different accounting systems into one
chart of accounts, builds a **13-week direct cash-flow forecast** as a single
event table, and models how **weather delays construction schedules and therefore
cash** — pushing back-loaded client billing past the horizon and into a **covenant
breach** under a wet quarter. Every figure on either dashboard traces back to the
raw CSV row behind it.

## One-paragraph architecture

Every forecast number is a **row** in one `cash_events` table — never a spreadsheet
cell. The five layers run in order: **(1) Ingestion** loads four accounting exports
(Gilde, Yuki, Exact, SnelStart), each with different delimiters, decimal styles,
date formats and account numbers; **(2) Reconciliation** applies `gl_mapping.csv` to
translate every system's accounts into one shared chart of accounts, producing a
unified `transactions` table that keeps `source_system` + `source_row_id` on every
row (unmapped accounts fall into an *“unmapped — review”* bucket instead of
crashing); **(3) Driver modelling** turns the forward milestone plan + opening
balances + weather into `cash_events` across five independently-tunable drivers
(materials, subcontractor, milestone_billing, payment_lag, weather) — and the
payment assumptions are **calibrated from the actuals** (empirical per-opco DSO/DPO,
clamped for noise, with the forward plan sanity-checked against the trailing
run-rate), so the past informs the forecast rather than the lags being hand-set; **(4) the
Scenario engine** transforms the *input* weather (wet ×1.6 / dry ×0.4) into
lost crew-days → a per-project schedule delay that **shifts** each weather-sensitive
project's billing and materials events to later weeks (tagged with the assumption
that moved them); and **(5) Role presentation** renders a CFO view (13-week forecast
by driver + covenant headroom) and an Opco MD view (WIP exposure + project risk),
with a role switcher, a scenario toggle, and a **click-to-trace audit drill-down**
that is simply a filter over the one `cash_events` table down to the originating raw
CSV row. The 13-week grid and every dashboard figure are computed **live** as
aggregations of `cash_events`; nothing is stored as a matrix.

## Run it (end-to-end)

```bash
# from the project root
python -m pip install -r requirements.txt

# 1. (re)generate the synthetic dataset — deterministic, seed 42
python scripts/generate_sample_data.py

# 2. launch the dashboards
python -m streamlit run app/streamlit_app.py
```

Then open the URL Streamlit prints (default http://localhost:8501). Use the **sidebar**
to switch **Role** (CFO / Opco MD) and **Scenario** (Base / Wet / Dry).

> The data is **synthetic** but realistic. It is produced by a seeded generator so it
> is reproducible and auditable, and so a controller can change the world (covenant
> pressure, weather severity, project mix) by editing the `CONFIG` block in
> `scripts/generate_sample_data.py` and re-running step 1.

## The demo, in three clicks

1. **CFO, Base scenario** → covenant indicator is **AMBER**: headroom thins to
   ~€152k in week 11 but holds above the €500k floor.
2. **Switch Scenario → Wet** → indicator goes **RED**: weather delays push
   back-loaded billing past week 13, liquidity falls ~€296k below the floor in
   weeks 11–12 (2 weeks breaching). Weather alone swings worst-week headroom by ~€448k.
3. **Audit drill-down** (bottom of either view) → pick the breach week, see every
   `cash_event` behind it, then trace one all the way to its row in
   `data/raw/milestones.csv` / `opening_balances.csv` / `weather_daily.csv`.

## Tuning (everything a controller needs is in `src/config.py`)

- **Driver parameters** — payment lags / terms, DSO/DPO (each driver independent).
- **Weather rule** — `precip_threshold_mm` (default 5), `frost_temp_c`,
  `crew_workdays_per_week`, and which drivers shift in time.
- **Scenarios** — precipitation scale factors for base/wet/dry.
- **Covenant** — liquidity floor, amber band, debt & EBITDA for the leverage test.

## Edge-case resilience (re-run after any of these — it absorbs them)

- **New GL account** — `7050` in Exact is intentionally *not* in the mapping; it lands
  in the **unmapped — review** bucket (shown in the sidebar) and never crashes.
- **Late correction journal** — a `CORRECTIE` reversal in each export; the pipeline is
  idempotent and re-runs cleanly.
- **Slipping project** — handled natively by the weather time-shift.

## Repository layout

```
data/raw/                 generated inputs (4 exports, GL map, balances, WIP,
                          milestones, weather, covenant terms)
scripts/
  generate_sample_data.py deterministic synthetic-data generator (seed 42)
src/
  config.py               all tunable parameters
  ingest.py               Layer 1 — per-system loaders (+ extensible registry)
  reconcile.py            Layer 2 — GL mapping -> unified transactions
  calibrate.py            derive DSO/DPO + run-rates from actuals (past -> forecast)
  weather.py              weather -> lost days -> per-week schedule delay
  drivers.py              Layer 3/4 — build cash_events (the single source of truth)
  covenant.py             liquidity path + headroom bands + leverage
  pipeline.py             orchestrator the UI calls
  audit.py                click-to-trace: cash_event/transaction -> raw CSV row
app/
  streamlit_app.py        Layer 5 — CFO + Opco MD dashboards
```

## `cash_events` schema (the one rule)

One row per future cash movement: `event_id`, `scenario`, `week` (1–13), `opco`,
`driver`, `amount` (signed: −outflow / +inflow), `source_system`, `source_table`,
`source_row_id`, `project_id`, `description`, `assumptions` (list of tags),
`operational_week`, `cash_date`, `beyond_horizon`.
