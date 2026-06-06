# Dakdekkersbedrijf Peter Ummels — Weather-Aware 13-Week Revenue Forecast

An honest, single-company dashboard that ingests **real** Exact FinTransactions
exports for **Dakdekkersbedrijf Peter Ummels** (a roofing firm in Brunssum),
reconciles each file to its `Eindsaldo`, and builds a **seasonal 13-week revenue
cash-flow forecast** from historical ISO-week patterns — then **nudges it with
real weather** (Open-Meteo historical climatology + the ECMWF **SEAS5** seasonal
forecast), because roofing revenue depends on workable (dry, frost-free) days.
Four role views (Owner / Operations / PE Board / Bookkeeper) in the company's
brand palette; every figure traces back to the source Excel cell behind it.

## One-paragraph architecture

Every forecast number is a **row** in one `forecast_events` table — never a
spreadsheet cell. The pipeline runs in order: **(1) Excel ingestion**
(`excel_ingest.py`) loads the 11 Exact FinTransactions exports (revenue/omzet
accounts 8000–8005 only), VAT-grosses net amounts (8005/8004 ×1.0, 8002 ×1.09),
and **reconciles each file to its Eindsaldo**; **(2) Seasonal forecast**
(`forecast.py`) aggregates historical weekly cash by ISO-week × year × VAT
category, then for each of the next 13 ISO weeks computes a prior-year mean
(2023–2025) scaled by a clamped YoY growth factor and shifted by a configurable
payment-lag assumption; **(3) Weather coupling** (`weather_forecast.py`) derives a
roofing *workability* index (lost day = rain > 5 mm or frost) from real Open-Meteo
data — the **SEAS5** 51-member seasonal ensemble for the forecast window vs the
2023+ historical climatology for the same ISO-weeks — and nudges each week's
revenue by a clamped factor (not a flat multiplier); **(4) Live presentation** —
the Streamlit app renders **four role views** (Owner, Operations & Weather, PE
Board, Bookkeeper) as live aggregations of `forecast_events` / `revenue_actuals`,
with an audit drill-down that traces any figure back through seed rows to the
literal Excel cell. The 13-week grid and every figure are computed **live**.

Legacy synthetic modules (`covenant.py`, `drivers.py`, `calibrate.py`,
`reconcile.py`, `weather.py`) remain in the repo but are not imported by the app.

## Run it

```bash
python -m pip install -r requirements.txt

# No real Exact data on hand? Generate a format-identical dev stand-in with
# realistic roofing seasonality (writes to data/actual_data/, gitignored):
python scripts/generate_dev_actuals.py

python -m streamlit run app/streamlit_app.py
```

The app reads the Exact FinTransactions exports from `data/actual_data/`
(revenue/omzet accounts only), reconciles each file to its `Eindsaldo`, builds a
**seasonal** 13-week forecast (prior-year same-ISO-week mean × clamped YoY ×
weather factor, shifted by a payment-lag assumption), and fetches **real weather**
from Open-Meteo (cached to `weather_data/` for a deterministic, offline demo).
Use the sidebar to switch **role** (Owner / Operations & Weather / PE Board /
Bookkeeper). Every figure traces to its source Excel cell.

**Not modelled** (no source data): costs/margin, covenant headroom, opening cash.
Weather *is* now modelled (SEAS5 + historical) and is toggleable via
`WEATHER_ADJUST` in `src/config.py`.

## Tuning (`src/config.py`)

- **Payment lag** — `PAYMENT_TERMS_DAYS` (default 30; set to `0` for invoice-date literalness).
- **Seasonal base** — `SEASONAL_YEARS` (prior years averaged for same-ISO-week mean).
- **YoY growth** — `YOY_CLAMP` band (e.g. 0.5–2.0) to avoid runaway extrapolation.
- **Horizon** — `FORECAST_START`, `N_WEEKS`.
- **Weather** — `WEATHER_ADJUST` (on/off), `WEATHER_RULE` (rain/frost thresholds),
  `WEATHER_FACTOR_CLAMP` (how far weather may move a week), `WEATHER_LOCATION`.

## Edge-case resilience

- **Unknown GL account** — routes to an `unmapped` category with a loud tag; never crashes.
- **File fails reconciliation** — surfaced as FAIL in the sidebar/table, not silently dropped.
- **Forward ISO-week with no prior-year history** — forecast 0 with an explicit `no seasonal base` tag.
- **Missing/locked Excel file** — reported in `recon_report` rather than aborting the whole run.

## Repository layout

```
data/actual_data/         Exact FinTransactions exports (gitignored; real or dev stand-in)
weather_data/             cached Open-Meteo responses (historical + SEAS5), committed
docs/weather/             weather dataset notes (location, periods, variables)
.streamlit/config.toml    Ummels brand theme
scripts/
  generate_dev_actuals.py format-identical dev data with roofing seasonality
src/
  config.py               tunable parameters (forecast + weather)
  excel_ingest.py         Layer 1 — parse + reconcile Excel exports
  forecast.py             Layer 2 — seasonal 13-week revenue forecast (weather-adjusted)
  weather_forecast.py     Layer 3 — Open-Meteo (SEAS5 + climatology) → weekly weather factor
  pipeline.py             orchestrator the UI calls
  audit.py                click-to-trace: forecast/actual → Excel row
app/
  streamlit_app.py        four role dashboards (Owner / Operations / PE Board / Bookkeeper)
```

## `forecast_events` schema

One row per forecast cash movement: `event_id`, `week` (1–13), `cash_date`,
`vat_category`, `amount` (cash, EUR), `assumptions` (list of tags),
`seed_event_ids` (historical actuals that produced this forecast cell),
`invoice_iso_week`.
