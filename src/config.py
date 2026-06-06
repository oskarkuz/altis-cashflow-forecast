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
# CALIBRATION — derive forecast assumptions from the reconciled ACTUALS
# (the past informs the future). Empirical DSO/DPO feed the payment_lag driver;
# the DRIVER_PARAMS values above are the fallback when calibration is off.
# --------------------------------------------------------------------------- #
CALIBRATE_FROM_ACTUALS = True
CALIBRATION = {
    "dso_min": 14, "dso_max": 49, "dso_default": 35,   # clamp band for noise
    "dpo_min": 20, "dpo_max": 49, "dpo_default": 25,
}

# --------------------------------------------------------------------------- #
# AI-ASSISTED GL MAPPING
# Unmapped accounts get an AI-suggested unified account + driver for a
# controller to approve. Default engine is an offline semantic matcher (no key,
# no cost). Set use_llm=True AND export ANTHROPIC_API_KEY to use real Claude.
# --------------------------------------------------------------------------- #
GL_AI = {
    "use_llm": False,
    "model": "claude-haiku-4-5-20251001",
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

# --------------------------------------------------------------------------- #
# WEATHER — real Open-Meteo data for the roofing company's location.
# Roofing is weather-sensitive: rain / frost / snow / high wind = lost workdays,
# which move revenue. We compare the SEAS5 SEASONAL FORECAST for the window
# against the historical CLIMATOLOGY for the same ISO-weeks and nudge the
# seasonal revenue forecast accordingly (not a flat multiplier).
# --------------------------------------------------------------------------- #
WEATHER_LOCATION = {"name": "Brunssum", "latitude": 50.9489, "longitude": 5.9725}
WEATHER_CACHE = os.path.join(ROOT, "weather_data")     # committed, deterministic
WEATHER_HISTORY_START = "2023-01-01"                   # climatology base
WEATHER_TZ = "Europe/Amsterdam"

# A roofing "lost day" rule (all thresholds tunable).
WEATHER_RULE = {
    "precip_mm": 5.0,      # > this much rain in a day = not workable on the roof
    "frost_c": 0.0,        # tmin <= this = frost = not workable
    "wind_kmh": 45.0,      # max wind above this = not workable (safety)
    "snow_cm": 0.0,        # any snowfall = not workable
}

# Couple weather into the forecast (toggle off to get the pure seasonal model).
WEATHER_ADJUST = True
WEATHER_FACTOR_CLAMP = (0.7, 1.3)   # how far weather may move a week's revenue

# Open-Meteo endpoints (fetched via curl, cached to WEATHER_CACHE for determinism).
OPENMETEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_SEASONAL = "https://seasonal-api.open-meteo.com/v1/seasonal"
WEATHER_DAILY_VARS = ["precipitation_sum", "temperature_2m_max",
                      "temperature_2m_min", "snowfall_sum", "wind_speed_10m_max"]

# --------------------------------------------------------------------------- #
# PORTFOLIO — the Altis PE portfolio of weather-exposed roofing companies.
# Each company sits at its own location (its own real Open-Meteo weather) and
# its own accounting platform. Only Ummels (Brunssum) ships with real Exact
# data; the other three use clearly-labelled demo financials + REAL weather
# until their exports are dropped into data/actual_data/<id>/.
# --------------------------------------------------------------------------- #
PORTFOLIO = [
    {"id": "ummels", "name": "Dakdekkersbedrijf Peter Ummels", "city": "Brunssum",
     "province": "Limburg", "lat": 50.9489, "lon": 5.9725,
     "system": "Exact Online (82604)", "real": True, "scale": 1.00, "seed": 42},
    {"id": "andijk", "name": "Altis Portfolio — Andijk", "city": "Andijk",
     "province": "Noord-Holland", "lat": 52.7453, "lon": 5.2200,
     "system": "Altis Dataset 1 (monthly)", "real": False, "scale": 0.55, "seed": 11},
    {"id": "heeze", "name": "Altis Portfolio — Heeze", "city": "Heeze",
     "province": "Noord-Brabant", "lat": 51.3812, "lon": 5.5730,
     "system": "SnelStart", "real": False, "scale": 0.80, "seed": 22},
    {"id": "winschoten", "name": "Altis Portfolio — Winschoten", "city": "Winschoten",
     "province": "Groningen", "lat": 53.1427, "lon": 7.0356,
     "system": "Gilde", "real": False, "scale": 0.70, "seed": 33},
]


def company_glob(company_id: str) -> str:
    return os.path.join(ROOT, "data", "actual_data", company_id, "*.xlsx")


def get_company(company_id: str) -> dict:
    return next((c for c in PORTFOLIO if c["id"] == company_id), PORTFOLIO[0])
