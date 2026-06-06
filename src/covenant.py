"""
COVENANT HEADROOM
Primary weekly test (read from covenant_terms.md, values in config.COVENANT):
    Available Liquidity = opening cash + cumulative net cash flow
    Headroom            = Available Liquidity - Liquidity Floor (EUR 500,000)
    Bands: GREEN headroom>=amber_threshold, AMBER 0<=headroom<amber, RED headroom<0
Secondary leverage test (informational, at week 13):
    Net Debt / LTM EBITDA <= 3.00x
"""
from __future__ import annotations

import pandas as pd

from . import config


def band(headroom: float) -> str:
    c = config.COVENANT
    if headroom < 0:
        return "RED"
    if headroom < c["amber_headroom"]:
        return "AMBER"
    return "GREEN"


def liquidity_path(cash_events: pd.DataFrame, opening_cash: float) -> pd.DataFrame:
    """Weekly liquidity + covenant headroom for the in-horizon cash_events."""
    floor = config.COVENANT["liquidity_floor"]
    inwin = cash_events[~cash_events["beyond_horizon"]]
    net = (inwin.groupby("week")["amount"].sum()
           .reindex(range(1, config.N_WEEKS + 1), fill_value=0.0))
    cumulative = net.cumsum()
    liquidity = opening_cash + cumulative
    headroom = liquidity - floor
    out = pd.DataFrame({
        "week": net.index,
        "net_cash": net.values,
        "liquidity": liquidity.values,
        "floor": floor,
        "headroom": headroom.values,
    })
    out["band"] = out["headroom"].map(band)
    return out


def leverage(end_liquidity: float) -> dict:
    c = config.COVENANT
    net_debt = c["total_debt"] - end_liquidity
    ratio = net_debt / c["ltm_ebitda"]
    return {
        "net_debt": net_debt,
        "ltm_ebitda": c["ltm_ebitda"],
        "ratio": ratio,
        "limit": c["leverage_max"],
        "pass": ratio <= c["leverage_max"],
        "headroom_turns": c["leverage_max"] - ratio,
    }


def summary(path: pd.DataFrame) -> dict:
    """Worst-week headroom + overall band for a scenario."""
    worst = path.loc[path["headroom"].idxmin()]
    lev = leverage(float(path.iloc[-1]["liquidity"]))
    return {
        "min_headroom": float(worst["headroom"]),
        "min_headroom_week": int(worst["week"]),
        "min_liquidity": float(worst["liquidity"]),
        "worst_band": band(float(worst["headroom"])),
        "end_liquidity": float(path.iloc[-1]["liquidity"]),
        "breaches": int((path["band"] == "RED").sum()),
        "leverage": lev,
    }
