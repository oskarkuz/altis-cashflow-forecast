"""
PIPELINE — the single orchestrator the UI calls.
Runs all five layers and returns one bundle of cached results for every scenario.
"""
from __future__ import annotations

import os

import pandas as pd

from . import config, covenant, drivers, ingest, reconcile, weather

SCENARIOS = list(config.SCENARIOS.keys())   # base, wet, dry


def opening_cash(raw_dir: str | None = None) -> float:
    raw_dir = raw_dir or config.RAW
    bal = pd.read_csv(os.path.join(raw_dir, "opening_balances.csv"))
    return float(bal.loc[bal["account_type"] == "cash", "amount"].sum())


def weekly_by_driver(cash_events: pd.DataFrame) -> pd.DataFrame:
    """13-week x driver matrix (in-horizon only) — computed live, never stored."""
    inwin = cash_events[~cash_events["beyond_horizon"]]
    piv = (inwin.pivot_table(index="week", columns="driver", values="amount",
                             aggfunc="sum", fill_value=0.0)
           .reindex(range(1, config.N_WEEKS + 1), fill_value=0.0))
    return piv


def run(raw_dir: str | None = None) -> dict:
    """Run the whole model. Returns a bundle dict consumed by the dashboards."""
    raw_dir = raw_dir or config.RAW

    # Layers 1-2: ingestion + reconciliation (scenario-independent)
    raw = ingest.load_all(raw_dir)
    txns = reconcile.reconcile(raw, raw_dir)
    recon_report = reconcile.reconciliation_report(txns)

    cash0 = opening_cash(raw_dir)

    # Layers 3-5 per scenario
    cash_events = {}
    weekly = {}
    liq = {}
    cov = {}
    wx = {}
    for sc in SCENARIOS:
        ev = drivers.build_cash_events(sc, raw_dir)
        cash_events[sc] = ev
        weekly[sc] = weekly_by_driver(ev)
        path = covenant.liquidity_path(ev, cash0)
        liq[sc] = path
        cov[sc] = covenant.summary(path)
        wx[sc] = weather.build_weather(sc, raw_dir)

    # all scenarios stacked (handy for the audit drill-down filter)
    all_events = pd.concat(cash_events.values(), ignore_index=True)

    return {
        "transactions": txns,
        "recon_report": recon_report,
        "opening_cash": cash0,
        "cash_events": cash_events,    # {scenario -> df}
        "all_events": all_events,
        "weekly": weekly,              # {scenario -> week x driver}
        "liquidity": liq,              # {scenario -> path df}
        "covenant": cov,               # {scenario -> summary}
        "weather": wx,                 # {scenario -> weather model}
        "scenarios": SCENARIOS,
    }
