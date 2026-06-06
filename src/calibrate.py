"""
CALIBRATION — make the PAST inform the FUTURE.
Derive forecast assumptions from the reconciled actuals instead of hard-coding
them, so history feeds the forward model:

  * empirical DSO (days sales outstanding)  = open AR / average daily revenue
  * empirical DPO (days payable outstanding) = open AP / average daily cost
  * historical weekly run-rate per driver, per opco (used to VALIDATE the
    forward committed plan)

Values are computed per operating company from the last ~quarter of postings
and clamped to a sane band (config.CALIBRATION) to absorb small-sample noise.
The clamped DSO/DPO feed the payment_lag driver; config values are the fallback.
"""
from __future__ import annotations

import pandas as pd

from . import config, drivers


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def calibrate(txns: pd.DataFrame, balances: pd.DataFrame | None = None,
              raw_dir: str | None = None) -> dict:
    raw_dir = raw_dir or config.RAW
    if balances is None:
        balances = drivers.load_opening_balances(raw_dir)
    bal = balances.copy()
    bal["amount"] = bal["amount"].astype(float)

    c = config.CALIBRATION
    span_days = max(1, (txns["posting_date"].max() - txns["posting_date"].min()).days)
    span_weeks = span_days / 7.0

    per_opco = {}
    for opco in sorted(txns["opco"].unique()):
        t = txns[txns["opco"] == opco]
        rev = t[(t["driver"] == "milestone_billing") & (t["amount"] > 0)]["amount"].sum()
        cost = -t[t["driver"].isin(["materials", "subcontractor"])]["amount"].sum()
        ar = bal[(bal["opco"] == opco) & (bal["account_type"] == "AR")]["amount"].sum()
        ap = -bal[(bal["opco"] == opco) & (bal["account_type"] == "AP")]["amount"].sum()

        daily_rev = rev / span_days
        daily_cost = cost / span_days
        dso_raw = (ar / daily_rev) if daily_rev > 0 else c["dso_default"]
        dpo_raw = (ap / daily_cost) if daily_cost > 0 else c["dpo_default"]

        per_opco[opco] = {
            "dso_days": int(round(_clamp(dso_raw, c["dso_min"], c["dso_max"]))),
            "dpo_days": int(round(_clamp(dpo_raw, c["dpo_min"], c["dpo_max"]))),
            "dso_raw": round(dso_raw, 1),
            "dpo_raw": round(dpo_raw, 1),
            "wk_materials": -t[t["driver"] == "materials"]["amount"].sum() / span_weeks,
            "wk_subcontractor": -t[t["driver"] == "subcontractor"]["amount"].sum() / span_weeks,
            "open_ar": float(ar),
            "open_ap": float(ap),
        }

    return {
        "enabled": True,
        "span_days": span_days,
        "span_weeks": round(span_weeks, 1),
        "per_opco": per_opco,
        # group-level historical weekly run-rate (for forecast validation)
        "hist_wk_materials": sum(p["wk_materials"] for p in per_opco.values()),
        "hist_wk_subcontractor": sum(p["wk_subcontractor"] for p in per_opco.values()),
    }


def summary_table(calib: dict) -> pd.DataFrame:
    """Per-opco calibrated assumptions, for display + audit."""
    rows = []
    for opco, p in calib["per_opco"].items():
        rows.append({
            "opco": opco,
            "open_AR": p["open_ar"], "DSO_raw": p["dso_raw"], "DSO_used": p["dso_days"],
            "open_AP": p["open_ap"], "DPO_raw": p["dpo_raw"], "DPO_used": p["dpo_days"],
            "hist_wk_materials": p["wk_materials"],
            "hist_wk_subcontractor": p["wk_subcontractor"],
        })
    return pd.DataFrame(rows)
