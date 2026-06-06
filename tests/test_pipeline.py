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
