# Altis Cash-Flow Forecast — Real-Data Honest Dashboard

**Date:** 2026-06-06
**Status:** Approved (design)
**Topic:** Replace the synthetic dataset with real accounting exports and rework the
app into an honest, single-company revenue cash-flow forecast.

## Problem

The current app (`src/pipeline.py` → `app/streamlit_app.py`) runs on a synthetic
dataset (`data/raw/*.csv`, seed 42) and models five drivers (milestone_billing,
materials, subcontractor, payment_lag, weather), a covenant test, WIP/project risk,
and base/wet/dry weather scenarios.

The real data in `data/actual_data/` does not support most of that model. It is
**revenue-only** (Dutch omzet GL accounts 8000–8005) and **historical** (past
postings, not a forward billing plan). Feeding it into the existing app would
require fabricating cost, weather, WIP, covenant and opening-balance inputs.

## Decisions (locked)

1. **Honest, real-only dashboard.** Show only what the real data supports.
   Drop — not fake — weather, covenant, WIP, opening cash, and the
   materials/subcontractor/payment_lag-runoff drivers.
2. **Single company: Dakdekkersbedrijf Peter Ummels** — the 11 Exact
   `FinTransactions` files under
   `data/actual_data/portfolio company 2 data-.../portfolio company 2 data/82604-*.xlsx`.
   (The "portfolio company 1" GB exports are a *different*, unnamed company — the
   shared 8002 code is coincidental: 8000–8005 are the standard NL chart. Excluded.)
3. **Seasonal forecast.** The 13-week forward number is derived from history:
   same ISO-week revenue across prior years, scaled by a clamped YoY growth factor.
4. **Drop the CFO/Opco-MD role switch and the base/wet/dry scenario toggle.**
5. **Payment lag is a clearly-labelled config knob** (`PAYMENT_TERMS_DAYS`,
   invoice→cash shift), default to a stated value, settable to `0` for pure
   invoice-date literalness. No AR aging exists in revenue accounts, so it is
   always tagged as an assumption.

## Data reality (verified)

- 11 Exact FinTransactions files, accounts **8005** (reverse charge, ×1.00),
  **8002** (9%, ×1.09), **8004** (0%, ×1.00). Years 2023 → May 2026, split into
  per-account/per-period files (`.2`, `.3` suffixes are additional accounts).
- Each file **reconciles to its own `Eindsaldo`** to the cent (the notebook's
  PASS check). ~€55M revenue across the span.
- This is **historical actuals**, not a forward plan.

## Architecture (Approach A — integrated real pipeline, app reworked in place)

```
excel_ingest  →  forecast (seasonal)  →  pipeline.run()  →  app (2 views)
                                            ↑ audit traces every figure to an Excel row
```

Reuse the notebook's proven Excel parser; add a seasonal forecast layer; rewrite
the pipeline bundle and the app. Synthetic modules (`weather.py`, `covenant.py`,
`drivers.py`, `calibrate.py`, `gl_ai.py`, `reconcile.py`) remain in the repo but are
no longer imported by the app (retirement is out of scope).

### 1. `src/excel_ingest.py` — ingestion + reconciliation

Port `parse_fintransactions`, `_normalise`, and the Eindsaldo reconciliation from
`notebooks/ingest.py`. Point it at the Dakdekkersbedrijf glob (new `config.ACTUAL_DATA`
path).

Returns:
- `revenue_actuals` (DataFrame): one row per ledger line — `date`, `gl_account`,
  `vat_category`, `vat_rate`, `net_amount`, `cash_amount` (VAT grossed-up),
  `debet`, `credit`, `doc_no`, `journal`, `event_id`, `source_file`,
  `source_excel_row`.
- `recon_report`: per-file `{file, rows, net_sum, eindsaldo, reconciles}` +
  totals.

### 2. `src/forecast.py` — seasonal model

1. Aggregate `revenue_actuals` → weekly cash by **ISO-week × year × vat_category**.
2. Forward horizon = 13 ISO weeks from `config.FORECAST_START`.
3. For each forward week, **seasonal base = mean of the same ISO-week's cash across
   available prior years (2023–2025)**, per vat_category. Averaging years damps
   single-week noise.
4. **YoY growth factor** = (2026 YTD cash ÷ 2025 same-period cash), **clamped** to a
   config band (e.g. 0.5–2.0) to avoid runaway extrapolation.
5. Apply **payment-lag** shift (`PAYMENT_TERMS_DAYS`) to move the forecast invoice
   week to a cash week.
6. Emit forecast `cash_events` (driver=`milestone_billing`), each carrying:
   `week` (1–13), `vat_category`, `amount` (cash), `assumptions`
   (`seasonal: ISO-wk N, 2023–25 mean × YoY 1.xx`, `cash incl. 9% BTW`,
   `payment lag Nd (assumption)`), and `seed_event_ids` — the historical
   `revenue_actuals` rows that produced it.

### 3. `src/pipeline.py` — rewritten `run()`

Returns one bundle (no scenarios, no covenant, no weather):
- `revenue_actuals`, `recon_report`
- `forecast_events`, `weekly_forecast` (13 × vat_category matrix, computed live)
- `seasonal_basis` (forward-week → contributing prior-year weeks + YoY factor)
- `kpis` (13-week forecast cash, YoY %, avg weekly forecast, trailing-13wk actual)

### 4. `src/audit.py` — trace to Excel

- `drill_down(forecast_events, week, vat_category)` — filter to the rows behind a cell.
- `trace_to_raw(event)`:
  - forecast event → list its `seed_event_ids` (the prior-year actuals behind it),
    each resolvable to its exact `source_file` + `source_excel_row`.
  - actuals row → its Excel file + row directly.
- Re-reads the source `.xlsx` row by `(source_file, source_excel_row)` so the
  displayed raw record is the literal cell values, not a re-derivation.

### 5. `app/streamlit_app.py` — rewritten

Drop roles, scenarios, covenant, weather, WIP, opening cash.

- **Sidebar:** company = Dakdekkersbedrijf (fixed); reconciliation status
  (files PASS/FAIL, total reconciled €); forecast-basis one-liner; an honest
  "what this data contains / omits" note.
- **View toggle:** Forecast · Actuals & history.
- **Forecast view:** KPI row (13wk forecast cash, YoY %, avg weekly) · 13-week
  stacked bar (cash by vat_category) · seasonal-basis table (how each week is
  derived) · audit drill-down.
- **Actuals & history view:** 3-year weekly/monthly revenue with YoY and the
  seasonality curve that justifies the forecast · per-file reconciliation table ·
  audit drill-down to Excel rows.

### 6. `src/config.py` — trim + additions

- Add `ACTUAL_DATA` path (Dakdekkersbedrijf glob).
- Add `PAYMENT_TERMS_DAYS` (default stated, e.g. 30; `0` = invoice-date literal).
- Add `YOY_CLAMP` band and `SEASONAL_YEARS` list.
- Keep `FORECAST_START`, `N_WEEKS`. Existing covenant/weather/scenario blocks remain
  but are unused by the app.

## Error handling

- **Unknown GL account** → routes to an `unmapped` category with a loud tag (notebook
  behaviour preserved); never crashes.
- **File fails reconciliation** → surfaced as FAIL in the sidebar/table, not silently
  dropped.
- **A forward ISO-week with no prior-year history** → forecast 0 for that
  week/category with an explicit `no seasonal base` tag.
- **Missing/locked Excel file** → ingestion reports it in `recon_report` rather than
  aborting the whole run.

## Testing

- **Reconciliation test:** for every Dakdekkersbedrijf file, summed `net_amount`
  equals the file's `Eindsaldo` to the cent.
- **Forecast determinism:** same inputs → same forecast (no randomness).
- **Audit round-trip:** every dashboard cell = Σ of its drill-down rows; each
  forecast event's `seed_event_ids` resolve to real Excel rows.
- **Edge cases:** empty forward week, unmapped account, payment-lag=0 vs >0.

## Out of scope

- Retiring/deleting the synthetic modules and the `data/raw/` generator.
- Company 1 (GB exports) as a second opco.
- Live LLM GL mapping.
- Any cost/weather/covenant/WIP modelling.
