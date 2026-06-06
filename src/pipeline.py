"""PIPELINE — the single orchestrator the UI calls (real-data, revenue-only).

Layers: ingest (real Excel) -> seasonal forecast -> live aggregations. No
scenarios / covenant / weather (no source data for them). Every figure is a
live aggregation of forecast_events / revenue_actuals, never a stored matrix.
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
        wk = forecast.weekly_actuals(actuals)
        last_13 = (wk[["iso_year", "iso_week"]].drop_duplicates()
                   .sort_values(["iso_year", "iso_week"]).tail(13))
        trailing = float(wk.merge(last_13, on=["iso_year", "iso_week"])["cash"].sum())
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
