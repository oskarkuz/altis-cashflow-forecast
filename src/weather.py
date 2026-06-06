"""
WEATHER MODULE  (the differentiator)
Daily precipitation + temperature  ->  workable vs lost crew-days  ->  a
cumulative schedule delay (in weeks) that later SHIFTS each weather-sensitive
project's milestone_billing and materials cash_events to later weeks.

Rule (all parameters, in config.WEATHER):
    lost day  <=>  precipitation > precip_threshold_mm  OR  temp_min <= frost_temp_c
Scenarios scale the INPUT precipitation (wet x1.6, dry x0.4), not the output cash.
"""
from __future__ import annotations

import os

import pandas as pd

from . import config


def load_weather(raw_dir: str | None = None) -> pd.DataFrame:
    raw_dir = raw_dir or config.RAW
    df = pd.read_csv(os.path.join(raw_dir, "weather_daily.csv"))
    df["date"] = pd.to_datetime(df["date"]).dt.date
    # forecast week 1..13 from the day index
    df = df.sort_values("date").reset_index(drop=True)
    df["week"] = (df.index // 7) + 1
    return df


def build_weather(scenario: str = "base", raw_dir: str | None = None) -> dict:
    """Return the weather->schedule model for one scenario.

    Keys:
      daily          : daily frame with scaled precip + lost flag
      lost_by_week   : {week -> lost crew-days that week}
      delay_by_week  : {week -> cumulative delay (weeks) for an event whose
                        OPERATIONAL week is `week`}  (lost-to-date / workdays)
      total_lost     : int
    """
    w = config.WEATHER
    scale = config.SCENARIOS[scenario]["precip_scale"]
    df = load_weather(raw_dir).copy()
    df["precip_scaled"] = df["precipitation_mm"] * scale
    df["lost"] = (df["precip_scaled"] > w["precip_threshold_mm"]) | \
                 (df["temp_min_c"] <= w["frost_temp_c"])

    lost_by_week = (df.groupby("week")["lost"].sum()
                    .reindex(range(1, config.N_WEEKS + 1), fill_value=0).astype(int))
    cum = lost_by_week.cumsum()
    delay_by_week = (cum // w["crew_workdays_per_week"]).astype(int)

    return {
        "scenario": scenario,
        "daily": df,
        "lost_by_week": lost_by_week.to_dict(),
        "delay_by_week": delay_by_week.to_dict(),
        "total_lost": int(lost_by_week.sum()),
    }
