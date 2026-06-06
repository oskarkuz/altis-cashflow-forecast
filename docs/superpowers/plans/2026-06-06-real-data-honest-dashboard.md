# Real-Data Honest Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synthetic dataset with the real Dakdekkersbedrijf Exact exports and rework the app into an honest, single-company, revenue-only 13-week cash-flow forecast driven by a seasonal model, with every figure traceable to its source Excel row.

**Architecture:** A new ingestion module ports the proven Excel parser (Exact FinTransactions → normalized revenue rows + Eindsaldo reconciliation). A new seasonal-forecast module projects the next 13 weeks from prior-year same-ISO-week revenue scaled by a clamped YoY factor, with a config payment-lag shift. `pipeline.run()` is rewritten to emit a real bundle; `audit.py` traces forecast cells back through seed rows to literal Excel cells; the Streamlit app is rewritten to two honest views (Forecast / Actuals & history). Weather/covenant/WIP/scenario/role code stays in the repo but is no longer imported.

**Tech Stack:** Python 3.10, pandas, openpyxl, streamlit, altair, pytest.

Spec: `docs/superpowers/specs/2026-06-06-altis-real-data-honest-dashboard-design.md`

---

## File Structure

- `requirements.txt` — add `openpyxl`, `pytest` (modify)
- `src/config.py` — add real-data path, GL map, forecast knobs (modify)
- `src/excel_ingest.py` — Excel → `revenue_actuals` DataFrame + reconciliation (create)
- `src/forecast.py` — seasonal forward model → forecast events + basis (create)
- `src/pipeline.py` — rewrite `run()` to emit the real bundle (rewrite)
- `src/audit.py` — drill-down + trace forecast/actuals → literal Excel row (rewrite)
- `app/streamlit_app.py` — two honest views, no roles/scenarios (rewrite)
- `tests/conftest.py` — synthetic FinTransactions `.xlsx` fixture + actuals builder (create)
- `tests/test_excel_ingest.py` (create)
- `tests/test_forecast.py` (create)
- `tests/test_pipeline.py` (create)
- `tests/test_audit.py` (create)

All `pytest` commands run from the project root via `.venv/bin/pytest`.

---

## Task 1: Dependencies + test scaffolding

**Files:**
- Modify: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Add deps to `requirements.txt`**

Append these two lines so the file reads:

```
pandas>=2.2
numpy>=1.26
streamlit>=1.40
altair>=5.0
openpyxl>=3.1
pytest>=8.0
```

- [ ] **Step 2: Install**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: openpyxl + pytest install (or "already satisfied").

- [ ] **Step 3: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 4: Create `tests/conftest.py` with the fixture builders**

```python
"""Shared test fixtures: build minimal Exact-FinTransactions .xlsx files that
match the real layout, and a helper to build an actuals DataFrame directly."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from openpyxl import Workbook


def make_fintransactions_xlsx(path, account_header, rows):
    """Write one Exact-FinTransactions-format workbook.

    account_header: e.g. "8002 - Omzet belast 9%"
    rows: list of (datum: date, debet: float, credit: float, doc_no: str, dagboek: str)
    Adds a trailing Eindsaldo row = sum(credit) - sum(debet).
    Layout mirrors the real files: a 'Grootboekrekening' criteria row carrying
    the account, a 'Nr.' data header, data rows
    [Nr, Per, Datum, Bkst.nr, Dagboek, Debet, Credit], then 'Eindsaldo'.
    """
    wb = Workbook()
    ws = wb.active
    ws.append(["Administratie: 82604 - Dakdekkersbedrijf Peter Ummels"])
    ws.append(["Datum: 4 juni 2026 door Test"])
    ws.append([" Kaart|Grootboekrekening"])
    ws.append([None])
    ws.append(["Criteria"])
    ws.append(["Grootboekrekening", account_header, "Boekjaar", 2026, "Periode", "1 - 12"])
    ws.append(["Nr.", "Per.", "Datum", "Bkst.nr.", "Dagboek", "Debet", "Credit"])
    tot_d = tot_c = 0.0
    for i, (datum, debet, credit, doc_no, dagboek) in enumerate(rows, start=1):
        ws.append([i, datum.month, datum, doc_no, dagboek, debet, credit])
        tot_d += debet
        tot_c += credit
    ws.append(["Totaal", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    ws.append(["Eindsaldo", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    wb.save(path)
    return str(path)


@pytest.fixture
def fintransactions_factory(tmp_path):
    """Return a builder that drops .xlsx files into a tmp dir and yields a glob
    matching them (for excel_ingest / pipeline)."""
    made = []

    def _make(name, account_header, rows):
        p = tmp_path / name
        made.append(make_fintransactions_xlsx(p, account_header, rows))
        return p

    _make.glob = str(tmp_path / "82604-*.xlsx")
    return _make


def make_actuals(records):
    """Build a revenue_actuals-shaped DataFrame directly (no Excel) for forecast/
    audit unit tests. records: list of dicts with at least
    date, gl_account, vat_category, vat_rate, net_amount, cash_amount, event_id."""
    df = pd.DataFrame(records)
    iso = df["date"].map(lambda d: d.isocalendar())
    df["iso_year"] = iso.map(lambda c: c[0])
    df["iso_week"] = iso.map(lambda c: c[1])
    return df
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "test: add deps and FinTransactions xlsx fixtures"
```

---

## Task 2: Config additions

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Add real-data + forecast config**

Append to the end of `src/config.py`:

```python
# --------------------------------------------------------------------------- #
# REAL DATA — Dakdekkersbedrijf Peter Ummels (Exact FinTransactions exports)
# Recursive glob is robust to the timestamped folder name.
# --------------------------------------------------------------------------- #
ACTUAL_DATA_GLOB = os.path.join(ROOT, "data", "actual_data", "**", "82604-*.xlsx")
COMPANY = "Dakdekkersbedrijf Peter Ummels"

# Chart of accounts -> (vat_category, vat_rate, label). Unknown -> unmapped.
GL_ACCOUNTS = {
    8000: ("omzet_hoog",    0.21, "Omzet hoog (21%)"),
    8001: ("omzet_verlegd", 0.00, "Omzet verlegd (reverse charge)"),
    8002: ("omzet_laag",    0.09, "Omzet laag (9%)"),
    8004: ("omzet_nul",     0.00, "Omzet 0% / niet bij u belast"),
    8005: ("omzet_verlegd", 0.00, "Omzet heffing verlegd (reverse charge)"),
}

# Seasonal forecast knobs (all tunable by a controller, like the rest of config).
PAYMENT_TERMS_DAYS = 30          # invoice -> cash shift; 0 = invoice-date literal
SEASONAL_YEARS = [2023, 2024, 2025]   # prior years averaged for the seasonal base
YOY_CLAMP = (0.5, 2.0)           # clamp band for the year-on-year growth factor
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/bin/python -c "from src import config; print(config.COMPANY, config.YOY_CLAMP, config.GL_ACCOUNTS[8002])"`
Expected: `Dakdekkersbedrijf Peter Ummels (0.5, 2.0) ('omzet_laag', 0.09, 'Omzet laag (9%)')`

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add real-data path, GL map, and seasonal forecast config"
```

---

## Task 3: Excel ingestion

**Files:**
- Create: `src/excel_ingest.py`
- Test: `tests/test_excel_ingest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_excel_ingest.py
import datetime as dt

from src import excel_ingest


def test_loads_rows_with_vat_gross_up(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-test.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 8, 12), 0.0, 1000.0, "INV1", "Verkoopboek")])
    actuals, recon = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert len(actuals) == 1
    row = actuals.iloc[0]
    assert row["gl_account"] == 8002
    assert row["vat_category"] == "omzet_laag"
    assert row["net_amount"] == 1000.0
    assert row["cash_amount"] == 1090.0          # 9% gross-up
    assert row["iso_year"] == 2026
    assert row["source_excel_row"] == 8          # 1-based excel row of the data line


def test_reverse_charge_not_grossed_up(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-rc.xlsx", "8005 - omzet heffing verlegd",
        [(dt.date(2026, 1, 6), 0.0, 500.0, "INV2", "Verkoopboek")])
    actuals, _ = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert actuals.iloc[0]["cash_amount"] == 500.0   # factor 1.00


def test_reconciliation_passes(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-r.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 3, 2), 0.0, 100.0, "A", "VB"),
         (dt.date(2026, 3, 9), 25.0, 0.0, "B", "VB")])
    _, recon = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert len(recon) == 1
    assert recon[0]["reconciles"] is True
    assert recon[0]["net_sum"] == 75.0           # 100 credit - 25 debet
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_excel_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.excel_ingest'`

- [ ] **Step 3: Implement `src/excel_ingest.py`**

```python
"""Excel ingestion — Exact FinTransactions exports -> revenue_actuals DataFrame.

Ported from notebooks/ingest.py (the parser is already reconciliation-verified
against the real Dakdekkersbedrijf files). Single company, revenue accounts only.
Every row keeps source_file + source_excel_row so any figure traces to its cell.
"""
from __future__ import annotations

import datetime as dt
import glob
import os

import pandas as pd
from openpyxl import load_workbook

from . import config


def _rows(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    return rows


def _cell(row, i):
    return row[i] if row and len(row) > i else None


def _num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def _to_int_account(v):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None


def _to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return None


def _doc_no(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return str(v).strip()


def classify(account):
    """account -> (vat_category, vat_rate, label). Unknown does not crash."""
    if account in config.GL_ACCOUNTS:
        return config.GL_ACCOUNTS[account]
    return ("unmapped", 0.0, f"ONGEMAPT grootboek {account} — map in config.GL_ACCOUNTS")


def parse_fintransactions(rows, source_file):
    """Return (list[dict] rows, eindsaldo). One dict per ledger line."""
    account = None
    for r in rows[:12]:
        if str(_cell(r, 0)).strip().lower().startswith("grootboekrekening"):
            account = _to_int_account(str(_cell(r, 1)).split(" - ")[0])
            break
    h = next((i for i, r in enumerate(rows) if str(_cell(r, 0)).strip() == "Nr."), None)
    if h is None:
        return [], None
    out, line, eindsaldo = [], 0, None
    for i, r in enumerate(rows[h + 1:], start=h + 2):   # +2 -> 1-based excel row
        first = _cell(r, 0)
        s = "" if first is None else str(first).strip()
        if s in ("", "None", "Totaal"):
            continue
        if s == "Eindsaldo":
            eindsaldo = round(_num(_cell(r, 6)) - _num(_cell(r, 5)), 2)
            continue
        line += 1
        vat_category, vat_rate, label = classify(account)
        net = round(_num(_cell(r, 6)) - _num(_cell(r, 5)), 2)
        cash = round(net * (1 + vat_rate), 2)
        date = _to_date(_cell(r, 2))
        out.append({
            "event_id": f"EX-{_doc_no(_cell(r, 3))}#L{line}",
            "date": date,
            "gl_account": account,
            "vat_category": vat_category,
            "vat_rate": vat_rate,
            "label": label,
            "net_amount": net,
            "cash_amount": cash,
            "debet": round(_num(_cell(r, 5)), 2),
            "credit": round(_num(_cell(r, 6)), 2),
            "doc_no": _doc_no(_cell(r, 3)),
            "journal": str(_cell(r, 4)).strip() if _cell(r, 4) else "",
            "source_file": source_file,
            "source_excel_row": i,
        })
    return out, eindsaldo


def load_revenue_actuals(glob_pattern=None):
    """Load + reconcile all matching files. Returns (actuals_df, recon_report)."""
    glob_pattern = glob_pattern or config.ACTUAL_DATA_GLOB
    all_rows, recon = [], []
    for path in sorted(glob.glob(glob_pattern, recursive=True)):
        fname = os.path.basename(path)
        rows = _rows(path)
        parsed, eindsaldo = parse_fintransactions(rows, fname)
        all_rows.extend(parsed)
        net_sum = round(sum(r["net_amount"] for r in parsed), 2)
        recon.append({
            "file": fname, "rows": len(parsed), "net_sum": net_sum,
            "eindsaldo": eindsaldo,
            "reconciles": eindsaldo is None or abs(net_sum - eindsaldo) < 0.01,
        })

    df = pd.DataFrame(all_rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "event_id", "date", "gl_account", "vat_category", "vat_rate", "label",
            "net_amount", "cash_amount", "debet", "credit", "doc_no", "journal",
            "source_file", "source_excel_row", "iso_year", "iso_week"])
        return df, recon

    # globally-unique event_id (doc/line collisions across files)
    dup = df["event_id"].duplicated(keep=False)
    df.loc[dup, "event_id"] = (df.loc[dup, "event_id"] + "@"
                               + df.loc[dup, "source_file"]
                               + "#" + df.loc[dup, "source_excel_row"].astype(str))
    iso = df["date"].map(lambda d: d.isocalendar() if d else (0, 0, 0))
    df["iso_year"] = iso.map(lambda c: c[0])
    df["iso_week"] = iso.map(lambda c: c[1])
    return df, recon
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_excel_ingest.py -v`
Expected: 3 passed.

- [ ] **Step 5: Sanity-check against real data**

Run:
```bash
.venv/bin/python -c "
from src import excel_ingest
df, rc = excel_ingest.load_revenue_actuals()
print('rows', len(df), 'files', len(rc), 'all_pass', all(r['reconciles'] for r in rc))
print('years', sorted(df['iso_year'].unique()), 'cats', sorted(df['vat_category'].unique()))
"
```
Expected: `rows 14574 files 11 all_pass True` and years incl 2023–2026, categories incl `omzet_laag`, `omzet_nul`, `omzet_verlegd`.

- [ ] **Step 6: Commit**

```bash
git add src/excel_ingest.py tests/test_excel_ingest.py
git commit -m "feat: real Excel ingestion with VAT gross-up and reconciliation"
```

---

## Task 4: Seasonal forecast

**Files:**
- Create: `src/forecast.py`
- Test: `tests/test_forecast.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_forecast.py
import datetime as dt

from src import forecast
from tests.conftest import make_actuals


def _rec(date, cat, net, rate, eid):
    return {"date": date, "gl_account": 8002, "vat_category": cat,
            "vat_rate": rate, "net_amount": net,
            "cash_amount": round(net * (1 + rate), 2), "event_id": eid}


def test_weekly_actuals_aggregates_by_iso_week_year_category():
    a = make_actuals([
        _rec(dt.date(2025, 3, 3), "omzet_laag", 100, 0.09, "e1"),
        _rec(dt.date(2025, 3, 4), "omzet_laag", 200, 0.09, "e2"),  # same ISO week
        _rec(dt.date(2025, 6, 2), "omzet_laag", 50, 0.09, "e3"),
    ])
    wk = forecast.weekly_actuals(a)
    march = wk[(wk["iso_year"] == 2025) & (wk["iso_week"] == 10)]
    assert march["cash"].iloc[0] == round(300 * 1.09, 2)


def test_yoy_factor_is_clamped():
    a = make_actuals([
        _rec(dt.date(2025, 1, 6), "omzet_laag", 100, 0.0, "p"),    # iso wk 2
        _rec(dt.date(2026, 1, 5), "omzet_laag", 1000, 0.0, "c"),   # iso wk 2, 10x
    ])
    # raw 10x -> clamped to upper bound 2.0
    assert forecast.yoy_factor(a, current_year=2026, prior_year=2025,
                               clamp=(0.5, 2.0)) == 2.0


def test_build_forecast_uses_prior_year_same_week_mean_times_yoy():
    # Two prior years, same ISO week as the forecast's first invoice week.
    start = dt.date(2026, 6, 8)              # cash week 1
    lag = 0                                  # invoice week == cash week
    iso_wk = start.isocalendar().week        # 24
    d24_2024 = dt.date.fromisocalendar(2024, iso_wk, 1)
    d24_2025 = dt.date.fromisocalendar(2025, iso_wk, 1)
    a = make_actuals([
        _rec(d24_2024, "omzet_laag", 1000, 0.0, "y24"),
        _rec(d24_2025, "omzet_laag", 3000, 0.0, "y25"),
    ])
    events, basis = forecast.build_forecast(
        a, start_date=start, n_weeks=13, payment_terms_days=lag,
        seasonal_years=[2024, 2025], yoy_clamp=(0.5, 2.0))
    wk1 = events[(events["week"] == 1) & (events["vat_category"] == "omzet_laag")].iloc[0]
    # mean(1000, 3000) = 2000 ; yoy = 1.0 (no 2026 actuals) -> 2000
    assert wk1["amount"] == 2000.0
    assert set(wk1["seed_event_ids"]) == {"y24", "y25"}
    assert len(events[events["vat_category"] == "omzet_laag"]) == 13


def test_empty_forward_week_forecasts_zero_with_tag():
    start = dt.date(2026, 6, 8)
    a = make_actuals([_rec(dt.date(2024, 1, 8), "omzet_laag", 100, 0.0, "x")])  # wk 2 only
    events, _ = forecast.build_forecast(
        a, start_date=start, n_weeks=1, payment_terms_days=0,
        seasonal_years=[2024], yoy_clamp=(0.5, 2.0))
    row = events.iloc[0]
    assert row["amount"] == 0.0
    assert any("no seasonal base" in t for t in row["assumptions"])
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_forecast.py -v`
Expected: FAIL — `No module named 'src.forecast'`

- [ ] **Step 3: Implement `src/forecast.py`**

```python
"""Seasonal forward forecast — the past informs the future.

Each forward CASH week k maps to an INVOICE ISO-week (k's date minus the payment
lag). The forecast cash for (week k, vat_category) = the mean of that ISO-week's
cash across prior seasonal years, scaled by a clamped year-on-year factor. Every
forecast event records the historical rows that seeded it.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from . import config


def weekly_actuals(actuals):
    """iso_year x iso_week x vat_category -> summed cash (long DataFrame)."""
    if actuals.empty:
        return pd.DataFrame(columns=["iso_year", "iso_week", "vat_category", "cash"])
    return (actuals.groupby(["iso_year", "iso_week", "vat_category"],
                            as_index=False)["cash_amount"].sum()
            .rename(columns={"cash_amount": "cash"}))


def yoy_factor(actuals, current_year=None, prior_year=None, clamp=None):
    """Growth factor = current-year-YTD cash / prior-year same-weeks cash, clamped."""
    clamp = clamp or config.YOY_CLAMP
    if actuals.empty:
        return 1.0
    current_year = current_year or int(actuals["iso_year"].max())
    prior_year = prior_year or current_year - 1
    cur = actuals[actuals["iso_year"] == current_year]
    if cur.empty:
        return 1.0
    max_wk = int(cur["iso_week"].max())
    cur_sum = cur["cash_amount"].sum()
    pri = actuals[(actuals["iso_year"] == prior_year)
                  & (actuals["iso_week"] <= max_wk)]
    pri_sum = pri["cash_amount"].sum()
    if pri_sum <= 0:
        return 1.0
    return round(min(max(cur_sum / pri_sum, clamp[0]), clamp[1]), 4)


def build_forecast(actuals, start_date=None, n_weeks=None, payment_terms_days=None,
                   seasonal_years=None, yoy_clamp=None):
    """Return (forecast_events, seasonal_basis) DataFrames."""
    start_date = start_date or config.FORECAST_START
    n_weeks = n_weeks or config.N_WEEKS
    payment_terms_days = config.PAYMENT_TERMS_DAYS if payment_terms_days is None \
        else payment_terms_days
    seasonal_years = seasonal_years or config.SEASONAL_YEARS
    yoy_clamp = yoy_clamp or config.YOY_CLAMP

    wk = weekly_actuals(actuals)
    factor = yoy_factor(actuals, clamp=yoy_clamp)
    cats = sorted(actuals["vat_category"].unique()) if not actuals.empty else []

    ev_rows, basis_rows = [], []
    for k in range(1, n_weeks + 1):
        cash_date = start_date + dt.timedelta(weeks=k - 1)
        invoice_date = cash_date - dt.timedelta(days=payment_terms_days)
        inv_wk = invoice_date.isocalendar().week
        for cat in cats:
            sub = wk[(wk["iso_week"] == inv_wk) & (wk["vat_category"] == cat)
                     & (wk["iso_year"].isin(seasonal_years))]
            seeds = actuals[(actuals["iso_week"] == inv_wk)
                            & (actuals["vat_category"] == cat)
                            & (actuals["iso_year"].isin(seasonal_years))]
            has_base = len(sub) > 0
            base_mean = float(sub["cash"].mean()) if has_base else 0.0
            amount = round(base_mean * factor, 2)
            if has_base:
                assumptions = [
                    f"seasonal: ISO-wk {inv_wk}, mean of {sorted(sub['iso_year'].tolist())}",
                    f"YoY x{factor:g}",
                ]
                lag_tag = (f"payment lag {payment_terms_days}d (assumption)"
                           if payment_terms_days else "invoice-date (no lag)")
                assumptions.append(lag_tag)
            else:
                assumptions = [f"no seasonal base for ISO-wk {inv_wk}"]
            ev_rows.append({
                "event_id": f"FC-W{k}-{cat}",
                "week": k,
                "cash_date": cash_date,
                "invoice_iso_week": inv_wk,
                "vat_category": cat,
                "driver": "milestone_billing",
                "amount": amount,
                "assumptions": assumptions,
                "seed_event_ids": seeds["event_id"].tolist(),
            })
            basis_rows.append({
                "week": k, "cash_date": cash_date, "invoice_iso_week": inv_wk,
                "vat_category": cat, "base_mean": round(base_mean, 2),
                "yoy_factor": factor, "amount": amount,
                "n_seed_rows": len(seeds),
                "seed_years": sorted(sub["iso_year"].tolist()),
            })
    return pd.DataFrame(ev_rows), pd.DataFrame(basis_rows)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_forecast.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/forecast.py tests/test_forecast.py
git commit -m "feat: seasonal forward forecast with clamped YoY and payment lag"
```

---

## Task 5: Pipeline rewrite

**Files:**
- Rewrite: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pipeline.py
import datetime as dt

from src import pipeline


def test_run_returns_real_bundle(fintransactions_factory):
    # one prior-year row in the forecast's first invoice week so forecast is non-zero
    iso_wk = dt.date(2026, 6, 8).isocalendar().week
    seed = dt.date.fromisocalendar(2025, iso_wk, 1)
    fintransactions_factory(
        "82604-2025-x.xlsx", "8002 - Omzet belast 9%",
        [(seed, 0.0, 1000.0, "S1", "VB")])
    b = pipeline.run(glob_pattern=fintransactions_factory.glob)
    assert set(b) >= {"revenue_actuals", "recon_report", "forecast_events",
                      "weekly_forecast", "seasonal_basis", "kpis", "company"}
    assert "scenarios" not in b and "covenant" not in b and "weather" not in b
    assert len(b["weekly_forecast"]) == 13           # 13 forecast weeks
    assert b["recon_report"]["all_pass"] is True
    assert b["kpis"]["forecast_total"] > 0


def test_weekly_by_category_shape(fintransactions_factory):
    fintransactions_factory(
        "82604-2025-y.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2025, 7, 1), 0.0, 500.0, "S2", "VB")])
    b = pipeline.run(glob_pattern=fintransactions_factory.glob)
    wf = b["weekly_forecast"]
    assert list(wf.index) == list(range(1, 14))      # weeks 1..13
    assert "omzet_laag" in wf.columns
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`
Expected: FAIL — `run()` signature/keys mismatch (old pipeline).

- [ ] **Step 3: Rewrite `src/pipeline.py`**

```python
"""PIPELINE — the single orchestrator the UI calls (real-data, revenue-only).

Layers: ingest (real Excel) -> seasonal forecast -> live aggregations. No
scenarios / covenant / weather (no source data for them). Every figure remains
a live aggregation of forecast_events / revenue_actuals, never a stored matrix.
"""
from __future__ import annotations

import pandas as pd

from . import config, excel_ingest, forecast


def weekly_by_category(forecast_events):
    """week x vat_category cash matrix (weeks 1..N), computed live."""
    if forecast_events.empty:
        return pd.DataFrame(index=range(1, config.N_WEEKS + 1))
    piv = (forecast_events.pivot_table(index="week", columns="vat_category",
                                       values="amount", aggfunc="sum",
                                       fill_value=0.0)
           .reindex(range(1, config.N_WEEKS + 1), fill_value=0.0))
    piv.columns.name = None
    return piv


def _kpis(actuals, forecast_events):
    forecast_total = float(forecast_events["amount"].sum()) if not forecast_events.empty else 0.0
    factor = forecast.yoy_factor(actuals)
    trailing = 0.0
    if not actuals.empty:
        wk = forecast.weekly_actuals(actuals).sort_values(["iso_year", "iso_week"])
        trailing = float(wk.tail(13 * max(1, actuals["vat_category"].nunique()))["cash"].sum())
    return {
        "forecast_total": round(forecast_total, 2),
        "avg_weekly": round(forecast_total / config.N_WEEKS, 2),
        "yoy_pct": round((factor - 1) * 100, 1),
        "trailing_13wk_actual": round(trailing, 2),
    }


def run(glob_pattern=None):
    actuals, recon = excel_ingest.load_revenue_actuals(glob_pattern)
    events, basis = forecast.build_forecast(actuals)
    recon_report = {
        "files": recon,
        "n_files": len(recon),
        "all_pass": all(r["reconciles"] for r in recon) if recon else False,
        "total_reconciled": round(sum(r["net_sum"] for r in recon), 2),
    }
    return {
        "company": config.COMPANY,
        "revenue_actuals": actuals,
        "recon_report": recon_report,
        "forecast_events": events,
        "weekly_forecast": weekly_by_category(events),
        "seasonal_basis": basis,
        "kpis": _kpis(actuals, events),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_pipeline.py -v`
Expected: 2 passed.

- [ ] **Step 5: Sanity-check on real data**

Run:
```bash
.venv/bin/python -c "
from src import pipeline
b = pipeline.run()
print('company', b['company'])
print('recon all_pass', b['recon_report']['all_pass'], 'files', b['recon_report']['n_files'])
print('kpis', b['kpis'])
print('weekly_forecast rows', len(b['weekly_forecast']), 'cols', list(b['weekly_forecast'].columns))
"
```
Expected: `all_pass True`, 11 files, 13 weekly rows, columns include omzet categories, positive forecast_total.

- [ ] **Step 6: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: rewrite pipeline.run to emit real revenue/forecast bundle"
```

---

## Task 6: Audit trace rewrite

**Files:**
- Rewrite: `src/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audit.py
import datetime as dt

from src import audit, excel_ingest, forecast
from tests.conftest import make_actuals


def _rec(date, net, eid):
    return {"date": date, "gl_account": 8002, "vat_category": "omzet_laag",
            "vat_rate": 0.09, "net_amount": net,
            "cash_amount": round(net * 1.09, 2), "event_id": eid}


def test_drill_down_filters_week_and_category():
    a = make_actuals([_rec(dt.date(2025, 6, 9), 100, "s1")])
    events, _ = forecast.build_forecast(
        a, start_date=dt.date(2026, 6, 8), n_weeks=13, payment_terms_days=0,
        seasonal_years=[2025])
    one = audit.drill_down(events, week=1, vat_category="omzet_laag")
    assert len(one) == 1 and one.iloc[0]["week"] == 1


def test_trace_seed_rows_resolves_actual_rows():
    a = make_actuals([_rec(dt.date(2025, 6, 9), 100, "s1"),
                      _rec(dt.date(2025, 6, 10), 200, "s2")])
    events, _ = forecast.build_forecast(
        a, start_date=dt.date(2026, 6, 8), n_weeks=13, payment_terms_days=0,
        seasonal_years=[2025])
    ev = audit.drill_down(events, week=1, vat_category="omzet_laag").iloc[0]
    seeds = audit.trace_seed_rows(ev, a)
    assert set(seeds["event_id"]) == {"s1", "s2"}


def test_read_excel_row_returns_literal_cells(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-z.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 4, 6), 0.0, 777.0, "INV9", "Verkoopboek")])
    actuals, _ = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    row = actuals.iloc[0]
    raw = audit.read_excel_row(row["source_file"], int(row["source_excel_row"]),
                               fintransactions_factory.glob)
    assert raw["raw_file"] == row["source_file"]
    assert 777.0 in [v for v in raw["row"].values()]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_audit.py -v`
Expected: FAIL — new functions not present in `audit.py`.

- [ ] **Step 3: Rewrite `src/audit.py`**

```python
"""AUDITABILITY — trace any dashboard figure to its literal source Excel cell.

drill_down()      -> the forecast_events behind a (week, vat_category) figure
trace_seed_rows() -> the historical revenue_actuals rows that seeded a forecast event
read_excel_row()  -> the literal cell values of one source .xlsx row
"""
from __future__ import annotations

import glob
import os

from openpyxl import load_workbook

from . import config

_FINTRANS_COLS = ["Nr.", "Per.", "Datum", "Bkst.nr.", "Dagboek", "Debet", "Credit"]


def drill_down(forecast_events, week=None, vat_category=None):
    """Filter forecast_events to the rows behind a dashboard cell."""
    df = forecast_events
    if week is not None:
        df = df[df["week"] == week]
    if vat_category is not None:
        df = df[df["vat_category"] == vat_category]
    return df.copy()


def trace_seed_rows(event, actuals):
    """Return the revenue_actuals rows that seeded one forecast event."""
    ids = event["seed_event_ids"]
    return actuals[actuals["event_id"].isin(ids)].copy()


def read_excel_row(source_file, source_excel_row, glob_pattern=None):
    """Open the originating .xlsx and return that row's labelled cell values."""
    glob_pattern = glob_pattern or config.ACTUAL_DATA_GLOB
    path = next((p for p in glob.glob(glob_pattern, recursive=True)
                 if os.path.basename(p) == source_file), None)
    if path is None:
        return {"raw_file": source_file, "key": source_excel_row, "row": None}
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    idx = source_excel_row - 1          # 1-based -> 0-based
    cells = rows[idx] if 0 <= idx < len(rows) else ()
    row = {}
    for i, col in enumerate(_FINTRANS_COLS):
        row[col] = cells[i] if i < len(cells) else None
    return {"raw_file": source_file, "key": source_excel_row, "row": row}
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/pytest tests/test_audit.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: all tests pass (excel_ingest 3, forecast 4, pipeline 2, audit 3).

- [ ] **Step 6: Commit**

```bash
git add src/audit.py tests/test_audit.py
git commit -m "feat: rewrite audit to trace forecast figures to source Excel cells"
```

---

## Task 7: Streamlit app rewrite

**Files:**
- Rewrite: `app/streamlit_app.py`

UI rendering is verified manually (Streamlit is impractical to unit-test); the data
it shows is already covered by the pipeline/audit tests.

- [ ] **Step 1: Rewrite `app/streamlit_app.py`**

```python
"""Altis — Dakdekkersbedrijf Peter Ummels: honest 13-week revenue cash-flow forecast.

Single company, revenue-only. Two views: Forecast (seasonal projection) and
Actuals & history. Every figure is a live aggregation of forecast_events /
revenue_actuals and traces to its source Excel cell. No weather/covenant/WIP/
scenarios — the source data does not contain them.
"""
from __future__ import annotations

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import audit, config, pipeline  # noqa: E402

st.set_page_config(page_title="Altis — Dakdekkersbedrijf Cash-Flow",
                   page_icon="💶", layout="wide")

CAT_LABELS = {
    "omzet_hoog": "Omzet hoog (21%)", "omzet_laag": "Omzet laag (9%)",
    "omzet_nul": "Omzet 0%", "omzet_verlegd": "Omzet verlegd (reverse charge)",
    "unmapped": "Unmapped",
}
CAT_COLORS = {
    "omzet_verlegd": "#2c7fb8", "omzet_hoog": "#fdae61",
    "omzet_laag": "#7fcdbb", "omzet_nul": "#c2a5cf", "unmapped": "#d73027",
}


def euro(x):
    return f"€{x:,.0f}"


@st.cache_data(show_spinner="Parsing the Exact exports and building the forecast…")
def load_bundle():
    return pipeline.run()


bundle = load_bundle()
actuals = bundle["revenue_actuals"]
events = bundle["forecast_events"]
rep = bundle["recon_report"]

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("Altis Groep")
st.sidebar.caption(f"13-week revenue cash-flow forecast · {bundle['company']}")
view = st.sidebar.radio("**View**", ["Forecast", "Actuals & history"], index=0)

st.sidebar.divider()
st.sidebar.markdown("**Reconciliation**")
flag = "✅" if rep["all_pass"] else "⚠️"
st.sidebar.write(f"- {flag} {rep['n_files']} files, "
                 f"{'all reconcile' if rep['all_pass'] else 'SOME FAIL'}")
st.sidebar.write(f"- Σ net reconciled: **{euro(rep['total_reconciled'])}**")
st.sidebar.caption(
    "Real Exact FinTransactions exports (revenue/omzet accounts only). The forecast "
    "is **seasonal**: each forward week = the mean of that ISO-week's revenue across "
    f"{config.SEASONAL_YEARS}, scaled by a clamped YoY factor, shifted by a "
    f"{config.PAYMENT_TERMS_DAYS}-day payment-lag assumption.")
st.sidebar.info(
    "**Not modelled** (no source data): weather, covenant headroom, WIP/project "
    "risk, opening cash, supplier/subcontractor costs.")


def cat_chart(long_df, x, y, title_y):
    return alt.Chart(long_df).mark_bar().encode(
        x=alt.X(f"{x}:O", title="Week"),
        y=alt.Y(f"{y}:Q", title=title_y, stack="zero"),
        color=alt.Color("vat_category:N",
                        scale=alt.Scale(domain=list(CAT_COLORS),
                                        range=list(CAT_COLORS.values())),
                        legend=alt.Legend(title="VAT category")),
        tooltip=["week:O", "vat_category:N", alt.Tooltip(f"{y}:Q", format=",.0f")])


def audit_panel():
    st.markdown("#### 🔎 Audit drill-down — trace a forecast figure to its Excel cell")
    cats = ["ALL"] + sorted(events["vat_category"].unique())
    c1, c2 = st.columns(2)
    wk = c1.selectbox("Week", list(range(1, config.N_WEEKS + 1)), key="aud_wk")
    cat = c2.selectbox("VAT category", cats, key="aud_cat")
    fil = audit.drill_down(events, week=int(wk),
                           vat_category=None if cat == "ALL" else cat)
    st.metric(f"Forecast cash — week {wk}, {cat}", euro(fil["amount"].sum()))
    show = fil.copy()
    show["assumptions"] = show["assumptions"].map(lambda a: "; ".join(a))
    show["seeds"] = show["seed_event_ids"].map(len)
    st.dataframe(show[["event_id", "week", "vat_category", "amount",
                       "invoice_iso_week", "seeds", "assumptions"]],
                 use_container_width=True, hide_index=True)

    seeded = fil[fil["seed_event_ids"].map(len) > 0]
    if len(seeded):
        st.markdown("**Trace one forecast event → its seeding actuals → a raw Excel row:**")
        ev_id = st.selectbox("forecast event", seeded["event_id"].tolist(), key="aud_ev")
        ev = seeded[seeded["event_id"] == ev_id].iloc[0]
        seeds = audit.trace_seed_rows(ev, actuals)
        st.caption(f"{len(seeds)} historical rows seed this forecast cell:")
        st.dataframe(seeds[["event_id", "date", "vat_category", "net_amount",
                            "cash_amount", "doc_no", "source_file",
                            "source_excel_row"]],
                     use_container_width=True, hide_index=True)
        if len(seeds):
            pick = st.selectbox("trace to Excel row", seeds["event_id"].tolist(),
                                key="aud_seed")
            s = seeds[seeds["event_id"] == pick].iloc[0]
            raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
            st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
            st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


# --------------------------------------------------------------------------- #
# FORECAST VIEW
# --------------------------------------------------------------------------- #
def forecast_view():
    k = bundle["kpis"]
    st.title("13-Week Revenue Cash-Flow Forecast")
    c1, c2, c3 = st.columns(3)
    c1.metric("Forecast cash (13 wk)", euro(k["forecast_total"]))
    c2.metric("Avg / week", euro(k["avg_weekly"]))
    c3.metric("YoY growth (applied)", f"{k['yoy_pct']:+.1f}%")

    st.subheader("Forecast cash by week and VAT category")
    wf = bundle["weekly_forecast"]
    long = wf.reset_index(names="week").melt("week", var_name="vat_category",
                                             value_name="amount")
    st.altair_chart(cat_chart(long, "week", "amount", "Forecast cash (€)"),
                    use_container_width=True)

    tbl = wf.copy()
    tbl["TOTAL"] = tbl.sum(axis=1)
    tbl.loc["TOTAL"] = tbl.sum()
    st.dataframe(tbl.style.format("{:,.0f}"), use_container_width=True)

    with st.expander("📐 Seasonal basis — how each week was derived", expanded=False):
        st.caption("Each forward week maps to an invoice ISO-week (cash date minus the "
                   "payment-lag assumption); the forecast = mean of that ISO-week's "
                   "revenue across prior years × the clamped YoY factor.")
        b = bundle["seasonal_basis"].copy()
        b["seed_years"] = b["seed_years"].map(lambda y: ", ".join(map(str, y)))
        st.dataframe(b[["week", "cash_date", "invoice_iso_week", "vat_category",
                        "base_mean", "yoy_factor", "amount", "n_seed_rows",
                        "seed_years"]].style.format(
            {"base_mean": "{:,.0f}", "amount": "{:,.0f}", "yoy_factor": "{:.2f}"}),
            use_container_width=True, hide_index=True)

    st.divider()
    audit_panel()


# --------------------------------------------------------------------------- #
# ACTUALS & HISTORY VIEW
# --------------------------------------------------------------------------- #
def actuals_view():
    st.title("Actuals & History — Reconciled Revenue")
    a = actuals.copy()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total revenue (cash, all years)", euro(a["cash_amount"].sum()))
    c2.metric("Ledger lines", f"{len(a):,}")
    c3.metric("Years", f"{a['iso_year'].min()}–{a['iso_year'].max()}")

    st.subheader("Weekly revenue by year")
    wk = (a.groupby(["iso_year", "iso_week"], as_index=False)["cash_amount"].sum())
    line = alt.Chart(wk).mark_line().encode(
        x=alt.X("iso_week:Q", title="ISO week"),
        y=alt.Y("cash_amount:Q", title="Revenue cash (€)"),
        color=alt.Color("iso_year:N", title="Year"),
        tooltip=["iso_year:N", "iso_week:Q",
                 alt.Tooltip("cash_amount:Q", format=",.0f")])
    st.altair_chart(line, use_container_width=True)

    st.subheader("Reconciliation by file")
    rec = pd.DataFrame(rep["files"])
    st.dataframe(rec.style.format({"net_sum": "{:,.2f}", "eindsaldo": "{:,.2f}"}),
                 use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🔎 Trace any actual posting to its Excel cell")
    yr = st.selectbox("Year", sorted(a["iso_year"].unique()), key="act_yr")
    sub = a[a["iso_year"] == yr].head(500)
    st.dataframe(sub[["event_id", "date", "vat_category", "net_amount",
                      "cash_amount", "doc_no", "source_file", "source_excel_row"]],
                 use_container_width=True, hide_index=True)
    pick = st.selectbox("posting", sub["event_id"].tolist(), key="act_ev")
    s = sub[sub["event_id"] == pick].iloc[0]
    raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
    st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
    st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


if view == "Forecast":
    forecast_view()
else:
    actuals_view()
```

- [ ] **Step 2: Manual smoke test**

Run: `.venv/bin/python -m streamlit run app/streamlit_app.py --server.headless true &`
then `sleep 8 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501` (expect `200`), then stop the process.
Also open the URL and confirm: sidebar shows 11 files reconciling; Forecast view renders the 13-week chart, basis table, and the audit drill-down resolves a forecast event → seed rows → a raw Excel row; Actuals view renders the weekly-by-year chart and the per-file reconciliation table.

- [ ] **Step 3: Commit**

```bash
git add app/streamlit_app.py
git commit -m "feat: rewrite app as honest single-company revenue forecast (2 views)"
```

---

## Task 8: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the "Run it" + data description sections**

Update `README.md` so the run instructions point at the real data (no synthetic
generator step) and the architecture paragraph reflects the revenue-only honest
scope. Replace the existing "Run it (end-to-end)" section body with:

```markdown
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
```

- [ ] **Step 2: Run the test suite once more**

Run: `.venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for real-data revenue forecast"
```

---

## Self-Review

**Spec coverage:**
- Honest real-only dashboard → Tasks 5, 7 (drop scenarios/covenant/weather/WIP) ✓
- Single company Dakdekkersbedrijf → Tasks 2 (`ACTUAL_DATA_GLOB`, `COMPANY`), 3 ✓
- Seasonal forecast (prior-year mean × clamped YoY) → Task 4 ✓
- Drop role switch + scenario toggle → Task 7 ✓
- Payment-lag config knob (0 = literal) → Tasks 2, 4 ✓
- VAT gross-up (8005/8004 ×1.0, 8002 ×1.09) → Task 3 ✓
- Reconciliation to Eindsaldo → Task 3 ✓
- Audit trace forecast → seed rows → Excel cell → Task 6, surfaced in Task 7 ✓
- Two views (Forecast / Actuals & history) → Task 7 ✓
- Error handling: unmapped account (Task 3 `classify`), failed reconciliation surfaced (Tasks 3/5/7), empty forward week → 0 + tag (Task 4), missing file → recon report not crash (Task 3) ✓
- Tests: reconciliation, determinism, audit round-trip, edge cases → Tasks 3–6 ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `load_revenue_actuals(glob_pattern)` → (df, recon list) used identically in Tasks 3/5/6. `build_forecast(...)` → (events, basis) used in Tasks 4/5/6. `forecast_events` columns (`week`, `vat_category`, `amount`, `assumptions`, `seed_event_ids`, `invoice_iso_week`) consistent across forecast/audit/app. `recon_report` is a dict with `files`/`n_files`/`all_pass`/`total_reconciled` in Tasks 5/7; the per-file list items use `file`/`rows`/`net_sum`/`eindsaldo`/`reconciles` from Task 3. `read_excel_row(source_file, source_excel_row, glob_pattern)` consistent in Tasks 6/7.
