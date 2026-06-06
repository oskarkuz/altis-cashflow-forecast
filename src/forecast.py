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
    current_year = start_date.year
    prior_year = current_year - 1
    factor = yoy_factor(actuals, current_year=current_year, prior_year=prior_year,
                        clamp=yoy_clamp)
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
