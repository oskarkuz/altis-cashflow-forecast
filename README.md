# Altis cash-flow forecast

13-week revenue forecast for four roofing companies in the Altis portfolio. Pulls revenue from Exact-style FinTransactions Excel exports, projects cash from historical weekly patterns, and adjusts for local weather (roofing work stops on wet or frosty days).

**Dakdekkersbedrijf Peter Ummels** (Brunssum) uses real Exact exports. The other three sites (Andijk, Heeze, Winschoten) use generated demo financials until their files are added — weather is real for all four.

Streamlit dashboard with four views: Owner, Operations & Weather, PE Board, Bookkeeper. Click any number to trace it back to the source Excel row.

## Quick start

```bash
uv sync

# No Excel files yet? Generate stand-in data with roofing seasonality:
uv run python scripts/generate_dev_actuals.py

uv run streamlit run app/streamlit_app.py
```

Drop exports in `data/actual_data/<company_id>/`. The app reconciles each file against its `Eindsaldo`, builds the forecast, and reads weather from cached Open-Meteo data in `weather_data/` (historical climatology + ECMWF SEAS5 seasonal forecast).

## How the forecast works

1. **Ingest** — Parse revenue GL accounts (8000–8005), gross up net amounts per VAT rate, reconcile to `Eindsaldo`.
2. **Seasonal base** — For each of the next 13 ISO weeks, average the same week across prior years (2023–2025), scale by a clamped YoY factor, shift by payment lag.
3. **Weather** — Compare forecast-period workability (SEAS5 ensemble) to historical climatology for those ISO weeks. A lost day is rain > 5 mm, frost, snow, or high wind. Revenue moves by a clamped factor per week.
4. **Display** — All numbers are computed on load from a single `forecast_events` table. No stored spreadsheet matrices.

**Out of scope** (no source data): costs, margins, covenant headroom, opening cash balance.

Toggle weather off with `WEATHER_ADJUST = False` in `src/config.py`.

## Configuration

Edit `src/config.py`:

| Parameter | What it does |
|-----------|--------------|
| `PAYMENT_TERMS_DAYS` | Days from invoice to expected cash (default 30; use 0 for invoice-date) |
| `SEASONAL_YEARS` | Years averaged for the seasonal base |
| `YOY_CLAMP` | Min/max bounds on the YoY growth factor |
| `FORECAST_START`, `N_WEEKS` | Forecast window |
| `WEATHER_RULE` | Rain, frost, wind, snow thresholds for a lost workday |
| `WEATHER_FACTOR_CLAMP` | How far weather can move a week's revenue |

## Project layout

```
data/actual_data/       Excel exports per company (gitignored)
weather_data/           Cached Open-Meteo responses (committed)
scripts/                Dev data generator
src/
  excel_ingest.py       Parse and reconcile exports
  forecast.py           Seasonal 13-week forecast
  weather_forecast.py   Workability index → weekly factors
  pipeline.py           Orchestrator (what the UI calls)
  audit.py              Trace figures to Excel rows
  config.py             All tunables
app/streamlit_app.py    Dashboard
```

Legacy modules (`covenant.py`, `drivers.py`, `calibrate.py`, `reconcile.py`, `weather.py`) are unused by the current app.

## `forecast_events` columns

One row per forecast cash movement:

`event_id`, `week` (1–13), `cash_date`, `vat_category`, `amount` (EUR), `assumptions` (tags), `seed_event_ids` (historical rows behind this forecast), `invoice_iso_week`

## Tests

```bash
uv run pytest
```
