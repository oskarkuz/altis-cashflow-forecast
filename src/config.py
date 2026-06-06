"""
config.py — every tunable parameter in ONE place.
A controller adjusts the forecast by editing values here; nothing is hard-coded
in the model logic. Each of the five drivers is independently tunable.
"""
from __future__ import annotations

import os
from datetime import date

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

# --------------------------------------------------------------------------- #
# Forecast horizon
# --------------------------------------------------------------------------- #
FORECAST_START = date(2026, 6, 8)   # Monday = first day of week 1
N_WEEKS = 13
TODAY = date(2026, 6, 6)

# --------------------------------------------------------------------------- #
# System -> operating company
# --------------------------------------------------------------------------- #
SYSTEM_TO_OPCO = {
    "exact":     "Altis Bouw BV",
    "gilde":     "Altis Infra BV",
    "yuki":      "Altis Installatie BV",
    "snelstart": "Altis Vastgoed BV",
}

# --------------------------------------------------------------------------- #
# DRIVER PARAMETERS  (each driver independently tunable)
# --------------------------------------------------------------------------- #
DRIVER_PARAMS = {
    # supplier payment lag: we pay material POs N days after they are committed
    "materials":          {"payment_lag_days": 14},
    # subcontractor payment lag: typically longer terms
    "subcontractor":      {"payment_lag_days": 30},
    # client payment terms: client pays us N days after a billing milestone
    "milestone_billing":  {"payment_terms_days": 21},
    # run-off of the OPENING balance sheet position over the first weeks
    "payment_lag":        {"dso_days": 35,   # days to collect opening AR
                           "dpo_days": 25},  # days to pay opening AP
    # weather idle / standby cost charged per EXTRA lost crew-day vs base
    "weather":            {"idle_cost_per_crew_day": 250.0},
}

# --------------------------------------------------------------------------- #
# WEATHER -> SCHEDULE rule (confirm threshold with a mentor; it is a parameter)
# --------------------------------------------------------------------------- #
WEATHER = {
    "precip_threshold_mm": 5.0,   # precipitation strictly above this = lost day
    "frost_temp_c": 0.0,          # temp_min at or below this = lost day (frost)
    "crew_workdays_per_week": 4,  # effective productive site-days per week
    # which drivers get shifted in TIME when a project slips (brief: billing+materials)
    "shift_drivers": ["milestone_billing", "materials"],
}

# Scenarios transform the *input* weather (precipitation), not the output cash.
SCENARIOS = {
    "base": {"precip_scale": 1.0},
    "wet":  {"precip_scale": 1.6},   # wet quarter: more rain -> more lost days
    "dry":  {"precip_scale": 0.4},   # dry quarter: less rain -> fewer lost days
}

# --------------------------------------------------------------------------- #
# COVENANT (read from data/raw/covenant_terms.md; values mirrored here)
# --------------------------------------------------------------------------- #
COVENANT = {
    "liquidity_floor": 500_000,     # weekly minimum available liquidity (EUR)
    "amber_headroom": 250_000,      # warn when headroom drops below this
    # secondary leverage covenant (informational, tested at week 13)
    "total_debt": 9_800_000,
    "ltm_ebitda": 3_600_000,
    "leverage_max": 3.00,
}
