"""
Layer 3/4 — DRIVER MODELLING  ->  cash_events
Build the single source of truth: one ROW per future cash movement.

Five drivers, each independently tunable (config.DRIVER_PARAMS):
  materials          (-)  forward project material POs            [weather-shifted]
  subcontractor      (-)  forward subcontractor commitments
  milestone_billing  (+)  forward client billing termijnen        [weather-shifted]
  payment_lag        (+/-) run-off of the OPENING AR / AP balances
  weather            (-)  idle/standby cost of EXTRA lost crew-days vs base

The weather cascade (the differentiator):
  a weather-sensitive project's milestone_billing & materials events are moved
  to later weeks by the cumulative delay from weather.build_weather(); each moved
  row is stamped with the assumption that moved it (e.g. "wet-quarter +2wk").

Every cash_event keeps source_system + source_row_id + source_table so any
figure traces back to a raw CSV row.
"""
from __future__ import annotations

import math
import os
from datetime import timedelta

import pandas as pd

from . import config, weather

CASH_EVENT_COLS = ["event_id", "scenario", "week", "opco", "driver", "amount",
                   "source_system", "source_table", "source_row_id",
                   "project_id", "description", "assumptions",
                   "operational_week", "cash_date", "beyond_horizon"]


# --------------------------------------------------------------------------- #
# loaders for the forward-looking inputs
# --------------------------------------------------------------------------- #
def load_projects(raw_dir: str) -> dict[str, dict]:
    df = pd.read_csv(os.path.join(raw_dir, "wip_projects.csv"))
    out = {}
    for _, r in df.iterrows():
        out[r["project_id"]] = {
            "opco": r["opco"],
            "weather_sensitive": str(r["weather_sensitive"]).strip().upper() == "Y",
            "crew_size": int(r["crew_size"]),
            "end_week": int(r["planned_end_week"]),
            "name": r["project_name"],
        }
    return out


def load_milestones(raw_dir: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(raw_dir, "milestones.csv"))
    df["planned_date"] = pd.to_datetime(df["planned_date"]).dt.date
    return df


def load_opening_balances(raw_dir: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(raw_dir, "opening_balances.csv"))
    return df


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _week_of(d) -> int:
    return (d - config.FORECAST_START).days // 7 + 1


def _system_of(opco: str) -> str:
    for sys, oc in config.SYSTEM_TO_OPCO.items():
        if oc == opco:
            return sys
    return "unknown"


# --------------------------------------------------------------------------- #
# driver builders
# --------------------------------------------------------------------------- #
def _events_from_milestones(scenario: str, projects: dict, milestones: pd.DataFrame,
                            wx: dict) -> list[dict]:
    events = []
    shift_drivers = config.WEATHER["shift_drivers"]
    delay_by_week = wx["delay_by_week"]
    for _, m in milestones.iterrows():
        pid = m["project_id"]
        proj = projects.get(pid, {})
        opco = proj.get("opco", "UNKNOWN")
        drv = m["driver"]
        op_week = int(m["planned_week"])
        op_date = m["planned_date"]

        # --- weather time-shift (only billing & materials of weather-sensitive projects) ---
        delay = 0
        assumptions = []
        if drv in shift_drivers and proj.get("weather_sensitive", False):
            delay = int(delay_by_week.get(op_week, 0))
            if delay > 0:
                assumptions.append(f"{scenario}-quarter +{delay}wk weather delay")
        shifted_date = op_date + timedelta(days=delay * 7)

        # --- payment timing lag (days) per driver ---
        params = config.DRIVER_PARAMS[drv]
        lag_days = params.get("payment_lag_days", params.get("payment_terms_days", 0))
        if lag_days:
            label = "payment terms" if drv == "milestone_billing" else "payment lag"
            assumptions.append(f"{lag_days}-day {label}")
        cash_date = shifted_date + timedelta(days=lag_days)
        week = _week_of(cash_date)
        beyond = week > config.N_WEEKS

        events.append({
            "scenario": scenario, "week": min(week, config.N_WEEKS) if beyond else week,
            "opco": opco, "driver": drv, "amount": float(m["amount"]),
            "source_system": _system_of(opco), "source_table": "milestones",
            "source_row_id": m["milestone_id"], "project_id": pid,
            "description": m["description"], "assumptions": assumptions,
            "operational_week": op_week, "cash_date": cash_date,
            "beyond_horizon": beyond,
        })
    return events


def _events_from_opening_balances(scenario: str, balances: pd.DataFrame,
                                  calibration: dict | None = None) -> list[dict]:
    """payment_lag driver: run-off the OPENING AR / AP over the first weeks.
    DSO/DPO are calibrated per-opco from the actuals when available, else config."""
    events = []
    cfg_dso = config.DRIVER_PARAMS["payment_lag"]["dso_days"]
    cfg_dpo = config.DRIVER_PARAMS["payment_lag"]["dpo_days"]
    for _, b in balances.iterrows():
        atype = b["account_type"]
        if atype == "cash":
            continue  # opening cash is the starting position, not a cash_event
        opco = b["opco"]
        if calibration and opco in calibration.get("per_opco", {}):
            dso = calibration["per_opco"][opco]["dso_days"]
            dpo = calibration["per_opco"][opco]["dpo_days"]
            src = "calibrated from actuals"
        else:
            dso, dpo, src = cfg_dso, cfg_dpo, "config default"
        amount = float(b["amount"])
        days = dso if atype == "AR" else dpo
        n_weeks = max(1, math.ceil(days / 7))
        slice_amt = amount / n_weeks
        tag = f"{days}-day {'DSO' if atype=='AR' else 'DPO'} run-off ({src})"
        for wk in range(1, n_weeks + 1):
            events.append({
                "scenario": scenario, "week": wk, "opco": b["opco"],
                "driver": "payment_lag", "amount": slice_amt,
                "source_system": b["source_system"], "source_table": "opening_balances",
                "source_row_id": b["balance_id"], "project_id": "",
                "description": f"Opening {atype} run-off ({wk}/{n_weeks})",
                "assumptions": [tag], "operational_week": 0,
                "cash_date": config.FORECAST_START + timedelta(days=(wk - 1) * 7),
                "beyond_horizon": False,
            })
    return events


def _events_from_weather(scenario: str, projects: dict, wx: dict,
                         wx_base: dict) -> list[dict]:
    """weather driver: idle/standby cost of EXTRA lost crew-days vs base.
    (Zero rows in the base scenario, since base is the reference.)"""
    events = []
    rate = config.DRIVER_PARAMS["weather"]["idle_cost_per_crew_day"]
    for pid, proj in projects.items():
        if not proj["weather_sensitive"]:
            continue
        for wk in range(1, proj["end_week"] + 1):
            extra = wx["lost_by_week"].get(wk, 0) - wx_base["lost_by_week"].get(wk, 0)
            if extra <= 0:
                continue
            cost = -extra * proj["crew_size"] * rate
            events.append({
                "scenario": scenario, "week": wk, "opco": proj["opco"],
                "driver": "weather", "amount": float(cost),
                "source_system": _system_of(proj["opco"]), "source_table": "weather",
                "source_row_id": f"WX-{pid}-W{wk}", "project_id": pid,
                "description": f"Idle crew cost {proj['name']} wk{wk}",
                "assumptions": [f"{scenario}: +{extra} lost day(s)", f"crew {proj['crew_size']}"],
                "operational_week": wk,
                "cash_date": config.FORECAST_START + timedelta(days=(wk - 1) * 7),
                "beyond_horizon": False,
            })
    return events


# --------------------------------------------------------------------------- #
# top-level
# --------------------------------------------------------------------------- #
def build_cash_events(scenario: str = "base", raw_dir: str | None = None,
                      calibration: dict | None = None) -> pd.DataFrame:
    raw_dir = raw_dir or config.RAW
    projects = load_projects(raw_dir)
    milestones = load_milestones(raw_dir)
    balances = load_opening_balances(raw_dir)

    wx = weather.build_weather(scenario, raw_dir)
    wx_base = weather.build_weather("base", raw_dir)

    events = []
    events += _events_from_milestones(scenario, projects, milestones, wx)
    events += _events_from_opening_balances(scenario, balances, calibration)
    events += _events_from_weather(scenario, projects, wx, wx_base)

    df = pd.DataFrame(events)
    df.insert(0, "event_id", [f"E-{scenario}-{i:05d}" for i in range(len(df))])
    return df[CASH_EVENT_COLS]
