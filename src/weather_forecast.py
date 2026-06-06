"""
WEATHER — real Open-Meteo data, coupled to the roofing revenue forecast.

Roofing is weather-sensitive: rain / frost = lost workdays = revenue that shifts
or shrinks. We do NOT use a flat multiplier. Instead:

  1. HISTORICAL climatology (Open-Meteo archive, Brunssum, 2023+): for each
     ISO-week, the typical fraction of *workable* roofing days.
  2. SEASONAL FORECAST (Open-Meteo SEAS5, 51-member ensemble): for each forward
     day, the PROBABILITY it is workable = the share of ensemble members with
     precip <= threshold AND tmin > frost. (Thresholding the ensemble *mean*
     would hide rainy days; the ensemble *spread* is the signal.)
  3. A per-week weather FACTOR = forward_workable / typical_workable (clamped).
     >1 = drier/milder than the ISO-week norm (nudge revenue up); <1 = wetter/
     colder (nudge down).

Fetched via curl (the box's Python CA store is stale) and cached to weather_data/
so the demo is deterministic and offline-repeatable. Any fetch failure degrades
to factor=1.0 (the pure seasonal model still runs).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.parse

import numpy as np
import pandas as pd

from . import config


# --------------------------------------------------------------------------- #
# fetch + cache (curl, because Python's CA store is expired on this box)
# --------------------------------------------------------------------------- #
def _curl_json(url: str, cache_file: str, refresh: bool = False):
    os.makedirs(config.WEATHER_CACHE, exist_ok=True)
    path = os.path.join(config.WEATHER_CACHE, cache_file)
    if os.path.exists(path) and not refresh and os.path.getsize(path) > 200:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    try:
        out = subprocess.run(["curl", "-sS", "--max-time", "180", url],
                             capture_output=True, text=True, timeout=200)
        data = json.loads(out.stdout)
        if "daily" not in data:
            raise ValueError(data.get("reason", "no daily block"))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return data
    except Exception as e:  # network/SSL/timeout -> caller degrades gracefully
        print(f"[weather] fetch failed ({cache_file}): {e}")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        return None


def _url(base: str, **params) -> str:
    return base + "?" + urllib.parse.urlencode(params, safe=",")


def _iso_cols(df: pd.DataFrame) -> pd.DataFrame:
    iso = df["date"].map(lambda d: d.isocalendar())
    df["iso_year"] = iso.map(lambda c: c[0])
    df["iso_week"] = iso.map(lambda c: c[1])
    return df


# --------------------------------------------------------------------------- #
# historical archive
# --------------------------------------------------------------------------- #
def load_history(refresh: bool = False) -> pd.DataFrame:
    loc = config.WEATHER_LOCATION
    r = config.WEATHER_RULE
    url = _url(config.OPENMETEO_ARCHIVE,
              latitude=loc["latitude"], longitude=loc["longitude"],
              start_date=config.WEATHER_HISTORY_START,
              end_date=config.TODAY.isoformat(),
              daily=",".join(config.WEATHER_DAILY_VARS), timezone=config.WEATHER_TZ)
    data = _curl_json(url, "historical_brunssum.json", refresh)
    if not data:
        return pd.DataFrame(columns=["date", "precip", "tmax", "tmin", "snow",
                                     "wind", "workable_frac", "iso_year", "iso_week"])
    d = data["daily"]
    df = pd.DataFrame({
        "date": pd.to_datetime(d["time"]).date,
        "precip": d.get("precipitation_sum"), "tmax": d.get("temperature_2m_max"),
        "tmin": d.get("temperature_2m_min"), "snow": d.get("snowfall_sum"),
        "wind": d.get("wind_speed_10m_max"),
    })
    df["workable_frac"] = ((df["precip"].fillna(0) <= r["precip_mm"]) &
                           (df["tmin"].fillna(99) > r["frost_c"])).astype(float)
    return _iso_cols(df)


# --------------------------------------------------------------------------- #
# SEAS5 seasonal forecast (ensemble -> daily workable PROBABILITY)
# --------------------------------------------------------------------------- #
def load_seas5(refresh: bool = False) -> pd.DataFrame:
    loc = config.WEATHER_LOCATION
    r = config.WEATHER_RULE
    url = _url(config.OPENMETEO_SEASONAL,
              latitude=loc["latitude"], longitude=loc["longitude"],
              daily="precipitation_sum,temperature_2m_max,temperature_2m_min",
              timezone=config.WEATHER_TZ)
    data = _curl_json(url, "seas5_brunssum.json", refresh)
    if not data:
        return pd.DataFrame(columns=["date", "precip", "tmax", "tmin",
                                     "workable_frac", "spread_precip",
                                     "iso_year", "iso_week"])
    d = data["daily"]

    def members(var):
        cols = {k[len(var):]: np.asarray(v, float)
                for k, v in d.items() if k == var or k.startswith(var + "_member")}
        return cols  # {suffix -> array over days}

    p = members("precipitation_sum")
    tn = members("temperature_2m_min")
    suff = sorted(set(p) & set(tn))
    # per member: workable boolean per day -> stack -> mean = daily probability
    stack = np.stack([(p[s] <= r["precip_mm"]) & (tn[s] > r["frost_c"]) for s in suff])
    workable_frac = stack.mean(axis=0)
    pmat = np.stack([p[s] for s in suff])
    df = pd.DataFrame({
        "date": pd.to_datetime(d["time"]).date,
        "precip": pmat.mean(axis=0),
        "tmax": np.stack([np.asarray(v, float)
                          for k, v in d.items()
                          if k.startswith("temperature_2m_max")]).mean(axis=0),
        "tmin": np.stack([tn[s] for s in suff]).mean(axis=0),
        "snow": 0.0, "wind": np.nan,
        "workable_frac": workable_frac, "spread_precip": pmat.std(axis=0),
    })
    return _iso_cols(df)


# --------------------------------------------------------------------------- #
# climatology + forward factors
# --------------------------------------------------------------------------- #
def _iso_week_dates(d: dt.date) -> list[dt.date]:
    monday = d - dt.timedelta(days=d.isocalendar().weekday - 1)
    return [monday + dt.timedelta(days=i) for i in range(7)]


def climatology(history: pd.DataFrame) -> dict[int, float]:
    """ISO-week -> typical workable-day fraction across the seasonal base years."""
    if history.empty:
        return {}
    h = history[history["iso_year"].isin(config.SEASONAL_YEARS)]
    return h.groupby("iso_week")["workable_frac"].mean().to_dict()


def weekly_factors(start_date=None, n_weeks=None, payment_terms_days=None):
    """Per forecast cash-week weather factor + a forward daily frame for display.
    factor = clamp(forward_workable_fraction / typical_workable_fraction)."""
    start_date = start_date or config.FORECAST_START
    n_weeks = n_weeks or config.N_WEEKS
    payment_terms_days = config.PAYMENT_TERMS_DAYS if payment_terms_days is None \
        else payment_terms_days
    clamp = config.WEATHER_FACTOR_CLAMP

    hist = load_history()
    seas = load_seas5()
    clim = climatology(hist)
    last_hist = max(hist["date"]) if not hist.empty else dt.date(2000, 1, 1)
    hist_by = {r.date: r.workable_frac for r in hist.itertuples()} if not hist.empty else {}
    seas_by = {r.date: r.workable_frac for r in seas.itertuples()} if not seas.empty else {}

    def day_frac(d):
        if d <= last_hist and d in hist_by:
            return hist_by[d]
        return seas_by.get(d, hist_by.get(d))

    factors = {}
    for k in range(1, n_weeks + 1):
        cash_date = start_date + dt.timedelta(weeks=k - 1)
        invoice_date = cash_date - dt.timedelta(days=payment_terms_days)
        iso_w = invoice_date.isocalendar().week
        fr, src = [], "history"
        for d in _iso_week_dates(invoice_date):
            v = day_frac(d)
            if v is None:
                continue
            fr.append(v)
            if d > last_hist:
                src = "SEAS5"
        fwd = float(np.mean(fr)) if fr else None
        typ = clim.get(iso_w)
        factor = 1.0 if (fwd is None or not typ) else \
            round(min(max(fwd / typ, clamp[0]), clamp[1]), 3)
        factors[k] = {
            "factor": factor,
            "forward_workable": None if fwd is None else round(fwd, 2),
            "typical_workable": None if typ is None else round(typ, 2),
            "lost_days": None if not fr else round(sum(1 - x for x in fr), 1),
            "invoice_iso_week": iso_w, "source": src,
        }

    end = start_date + dt.timedelta(weeks=n_weeks)
    fd = (seas[(seas["date"] >= config.TODAY) & (seas["date"] <= end)].copy()
          if not seas.empty else pd.DataFrame())
    return factors, fd


def summary(factors: dict) -> dict:
    vals = [f["factor"] for f in factors.values()]
    lost = sum((f["lost_days"] or 0) for f in factors.values())
    return {
        "mean_factor": round(sum(vals) / len(vals), 3) if vals else 1.0,
        "weeks_drier": sum(1 for v in vals if v > 1.02),
        "weeks_wetter": sum(1 for v in vals if v < 0.98),
        "expected_lost_days": round(lost, 1),
    }
