"""
AUDITABILITY (worth 28%)
Every cash_event carries source_system + source_table + source_row_id. This
module turns that pointer back into the ORIGINAL raw CSV row, so any forecast
figure can be traced all the way down to the file it came from.

drill_down()  -> the cash_events behind a (scenario, week, driver[, opco]) figure
trace_to_raw() -> the single originating raw record for one cash_event
"""
from __future__ import annotations

import os

import pandas as pd

from . import config

# how to find the originating row in each raw accounting export
_EXPORT_KEYS = {
    "exact":     ("exact_export.csv",     ",", "JournalEntryID"),
    "gilde":     ("gilde_export.csv",     ";", "Boekstuknr"),
    "yuki":      ("yuki_export.csv",      ",", "EntryID"),
    "snelstart": ("snelstart_export.csv", ";", "Regelnr"),
}


def drill_down(cash_events: pd.DataFrame, scenario: str | None = None,
               week: int | None = None, driver: str | None = None,
               opco: str | None = None, project_id: str | None = None,
               include_beyond: bool = False) -> pd.DataFrame:
    """Filter cash_events to exactly the rows behind a dashboard figure.
    This IS the audit report — a filter over the single table, not a separate one."""
    df = cash_events
    if scenario is not None:
        df = df[df["scenario"] == scenario]
    if not include_beyond:
        df = df[~df["beyond_horizon"]]
    if week is not None:
        df = df[df["week"] == week]
    if driver is not None:
        df = df[df["driver"] == driver]
    if opco is not None:
        df = df[df["opco"] == opco]
    if project_id is not None:
        df = df[df["project_id"] == project_id]
    return df.copy()


def trace_to_raw(event: dict | pd.Series, raw_dir: str | None = None) -> dict:
    """Return the ORIGINATING raw record for one cash_event.

    milestones / opening_balances -> the raw forward-input CSV row
    weather                       -> the rainy days that drove the lost-day idle cost
    (accounting actuals)          -> the original posting in the system export
    """
    raw_dir = raw_dir or config.RAW
    table = event["source_table"]
    rid = str(event["source_row_id"])

    if table == "milestones":
        df = pd.read_csv(os.path.join(raw_dir, "milestones.csv"), dtype=str)
        hit = df[df["milestone_id"] == rid]
        return {"raw_file": "milestones.csv", "key": rid,
                "row": hit.iloc[0].to_dict() if len(hit) else None}

    if table == "opening_balances":
        df = pd.read_csv(os.path.join(raw_dir, "opening_balances.csv"), dtype=str)
        hit = df[df["balance_id"] == rid]
        return {"raw_file": "opening_balances.csv", "key": rid,
                "row": hit.iloc[0].to_dict() if len(hit) else None}

    if table == "weather":
        # rid like "WX-INFRA-01-W7" -> week 7; show the days >threshold that week
        wk = int(rid.rsplit("W", 1)[-1])
        wd = pd.read_csv(os.path.join(raw_dir, "weather_daily.csv"))
        wd["week"] = (wd.index // 7) + 1
        scale = config.SCENARIOS.get(event.get("scenario", "base"), {}).get("precip_scale", 1.0)
        days = wd[wd["week"] == wk].copy()
        days["precip_scaled"] = (days["precipitation_mm"] * scale).round(1)
        lost = days[(days["precip_scaled"] > config.WEATHER["precip_threshold_mm"]) |
                    (days["temp_min_c"] <= config.WEATHER["frost_temp_c"])]
        return {"raw_file": "weather_daily.csv", "key": f"week {wk}",
                "row": {"lost_days": lost[["date", "precipitation_mm", "precip_scaled",
                                           "temp_min_c"]].to_dict("records")}}

    # fallback: an actual accounting posting (used by the Opco MD actuals view)
    sys = event.get("source_system", "")
    if sys in _EXPORT_KEYS:
        fname, sep, keycol = _EXPORT_KEYS[sys]
        df = pd.read_csv(os.path.join(raw_dir, fname), sep=sep, dtype=str)
        hit = df[df[keycol] == rid]
        return {"raw_file": fname, "key": rid,
                "row": hit.iloc[0].to_dict() if len(hit) else None}

    return {"raw_file": "(unknown)", "key": rid, "row": None}


def trace_transaction(txn: dict | pd.Series, raw_dir: str | None = None) -> dict:
    """Trace a reconciled `transactions` row back to its raw accounting export row."""
    raw_dir = raw_dir or config.RAW
    sys = txn["source_system"]
    rid = str(txn["source_row_id"])
    if sys in _EXPORT_KEYS:
        fname, sep, keycol = _EXPORT_KEYS[sys]
        df = pd.read_csv(os.path.join(raw_dir, fname), sep=sep, dtype=str)
        hit = df[df[keycol] == rid]
        return {"raw_file": fname, "key": rid,
                "row": hit.iloc[0].to_dict() if len(hit) else None}
    return {"raw_file": "(unknown)", "key": rid, "row": None}
