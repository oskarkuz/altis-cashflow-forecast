# Altis Groep — Real-Data 13-Week Revenue Forecast

An honest, single-company dashboard that ingests **real** Exact FinTransactions
exports for **Dakdekkersbedrijf Peter Ummels**, reconciles each file to its
`Eindsaldo`, and builds a **seasonal 13-week revenue cash-flow forecast** from
historical ISO-week patterns. Every figure traces back to the source Excel cell
behind it.

## One-paragraph architecture

Every forecast number is a **row** in one `forecast_events` table — never a
spreadsheet cell. The pipeline runs in order: **(1) Excel ingestion**
(`excel_ingest.py`) loads the 11 Exact FinTransactions exports (revenue/omzet
accounts 8000–8005 only), VAT-grosses net amounts (8005/8004 ×1.0, 8002 ×1.09),
and **reconciles each file to its Eindsaldo**; **(2) Seasonal forecast**
(`forecast.py`) aggregates historical weekly cash by ISO-week × year × VAT
category, then for each of the next 13 ISO weeks computes a prior-year mean
(2023–2025) scaled by a clamped YoY growth factor and shifted by a configurable
payment-lag assumption; **(3) Live presentation** — the Streamlit app renders two
views (Forecast / Actuals & history) as live aggregations of `forecast_events`
and `revenue_actuals`, with an audit drill-down that traces any figure back
through seed rows to the literal Excel cell. The 13-week grid and every
dashboard figure are computed **live**; nothing is stored as a matrix.

Legacy synthetic modules (`weather.py`, `covenant.py`, `drivers.py`,
`calibrate.py`, `reconcile.py`) remain in the repo but are no longer imported
by the app.

## Run it

```bash
python -m pip install -r requirements.txt
python -m streamlit run app/streamlit_app.py
```

The app reads the real Exact FinTransactions exports for **Dakdekkersbedrijf Peter
Ummels** from `data/actual_data/` (revenue/omzet accounts only), reconciles each
file to its `Eindsaldo`, and builds a **seasonal** 13-week revenue cash-flow
forecast (prior-year same-ISO-week mean × clamped YoY, shifted by a payment-lag
assumption). Use the sidebar to switch **View** (Forecast / Actuals & history).
Every figure traces to its source Excel cell.

**Not modelled** (no source data): weather scenarios, covenant headroom, WIP/
project risk, opening cash, supplier/subcontractor costs. Tunable knobs live in
`src/config.py` (`PAYMENT_TERMS_DAYS`, `SEASONAL_YEARS`, `YOY_CLAMP`).

## Tuning (`src/config.py`)

- **Payment lag** — `PAYMENT_TERMS_DAYS` (default 30; set to `0` for invoice-date literalness).
- **Seasonal base** — `SEASONAL_YEARS` (prior years averaged for same-ISO-week mean).
- **YoY growth** — `YOY_CLAMP` band (e.g. 0.5–2.0) to avoid runaway extrapolation.
- **Horizon** — `FORECAST_START`, `N_WEEKS`.

## Edge-case resilience

- **Unknown GL account** — routes to an `unmapped` category with a loud tag; never crashes.
- **File fails reconciliation** — surfaced as FAIL in the sidebar/table, not silently dropped.
- **Forward ISO-week with no prior-year history** — forecast 0 with an explicit `no seasonal base` tag.
- **Missing/locked Excel file** — reported in `recon_report` rather than aborting the whole run.

## Repository layout

```
data/actual_data/         real Exact FinTransactions exports (gitignored)
data/raw/                 legacy synthetic inputs (unused by app)
src/
  config.py               tunable parameters
  excel_ingest.py         Layer 1 — parse + reconcile Excel exports
  forecast.py             Layer 2 — seasonal 13-week revenue forecast
  pipeline.py             orchestrator the UI calls
  audit.py                click-to-trace: forecast/actual → Excel row
app/
  streamlit_app.py        Forecast + Actuals & history dashboards
```

## `forecast_events` schema

One row per forecast cash movement: `event_id`, `week` (1–13), `cash_date`,
`vat_category`, `amount` (cash, EUR), `assumptions` (list of tags),
`seed_event_ids` (historical actuals that produced this forecast cell),
`invoice_iso_week`.
