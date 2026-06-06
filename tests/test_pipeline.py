# tests/test_pipeline.py
import datetime as dt

import pandas as pd

from src import pipeline
from tests.conftest import make_actuals


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


def test_trailing_13wk_actual_uses_last_13_distinct_weeks():
    # 15 distinct ISO weeks in 2025 for category A; category B is sparse (only weeks 1-2).
    # tail(13 * n_categories) = tail(26) would pull in rows from weeks 1-2 of cat A too,
    # overstating the result.  The fix must sum exactly the last 13 distinct calendar weeks.
    recs = []
    for w in range(1, 16):
        d = dt.date.fromisocalendar(2025, w, 1)
        recs.append({"date": d, "gl_account": 8002, "vat_category": "omzet_laag",
                     "vat_rate": 0.0, "net_amount": w * 100,
                     "cash_amount": float(w * 100), "event_id": f"e{w}_a"})
    # Category B only present in weeks 1–2 (sparse)
    for w in range(1, 3):
        d = dt.date.fromisocalendar(2025, w, 1)
        recs.append({"date": d, "gl_account": 8001, "vat_category": "omzet_hoog",
                     "vat_rate": 0.0, "net_amount": 5000,
                     "cash_amount": 5000.0, "event_id": f"e{w}_b"})
    a = make_actuals(recs)
    k = pipeline._kpis(a, pd.DataFrame())
    # Last 13 distinct weeks are 3..15 (cat A only, since B ends at week 2)
    expected = sum(w * 100 for w in range(3, 16))
    assert k["trailing_13wk_actual"] == expected
