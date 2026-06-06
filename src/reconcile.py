"""
Layer 2 — RECONCILIATION
Translate each system's own account numbers into ONE shared chart of accounts
using gl_mapping.csv. Output a unified `transactions` table that keeps
source_system + source_row_id on every row (full traceability).

Edge-case resilience: an account number not present in the mapping is NOT an
error. It is routed to driver='UNMAPPED' / unified_account='UNMAPPED' so the
pipeline keeps running and a controller can review the bucket.
"""
from __future__ import annotations

import os

import pandas as pd

from . import config, ingest

UNIFIED_COLS = ["txn_id", "source_system", "source_row_id", "opco",
                "posting_date", "source_account", "unified_account",
                "unified_name", "driver", "project_id", "counterparty", "amount"]


def load_mapping(raw_dir: str | None = None) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(source_system, source_account) -> (unified_account, unified_name, driver)."""
    raw_dir = raw_dir or config.RAW
    gm = pd.read_csv(os.path.join(raw_dir, "gl_mapping.csv"), dtype=str).fillna("")
    mapping = {}
    for _, r in gm.iterrows():
        key = (r["source_system"].strip(), r["source_account"].strip())
        mapping[key] = (r["unified_account"].strip(),
                        r["unified_name"].strip(),
                        r["driver"].strip())
    return mapping


def reconcile(raw_df: pd.DataFrame | None = None,
              raw_dir: str | None = None) -> pd.DataFrame:
    """Apply the GL mapping -> unified transactions table."""
    raw_dir = raw_dir or config.RAW
    if raw_df is None:
        raw_df = ingest.load_all(raw_dir)
    mapping = load_mapping(raw_dir)

    rows = []
    for i, r in raw_df.reset_index(drop=True).iterrows():
        key = (r["source_system"], str(r["source_account"]).strip())
        ua, un, drv = mapping.get(
            key, ("UNMAPPED", f"(unmapped: {r['source_account']} — review)", "UNMAPPED"))
        rows.append({
            "txn_id": f"T{i:06d}",
            "source_system": r["source_system"],
            "source_row_id": r["source_row_id"],
            "opco": config.SYSTEM_TO_OPCO.get(r["source_system"], "UNKNOWN"),
            "posting_date": r["posting_date"],
            "source_account": r["source_account"],
            "unified_account": ua,
            "unified_name": un,
            "driver": drv,
            "project_id": r["project_id"],
            "counterparty": r["counterparty"],
            "amount": float(r["amount"]),
        })
    return pd.DataFrame(rows, columns=UNIFIED_COLS)


def reconciliation_report(txns: pd.DataFrame) -> dict:
    """Quick health summary for the demo / Opco MD view."""
    unmapped = txns[txns["driver"] == "UNMAPPED"]
    return {
        "n_transactions": len(txns),
        "n_systems": txns["source_system"].nunique(),
        "n_unmapped": len(unmapped),
        "unmapped_accounts": sorted(unmapped["source_account"].unique().tolist()),
        "by_system": txns.groupby("source_system").size().to_dict(),
        "by_driver": txns.groupby("driver")["amount"].sum().round(0).to_dict(),
    }
