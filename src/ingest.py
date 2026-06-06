"""
Layer 1 — INGESTION
Load the four accounting exports. Each system has different column names,
delimiters, decimal styles and date formats. Every loader normalises to ONE
raw shape while preserving source_system + source_row_id for traceability.

Normalised columns returned by every loader:
    source_system, source_row_id, posting_date (date),
    source_account (str), source_account_name, project_id,
    counterparty, amount (signed float; outflow < 0, inflow > 0)
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from . import config

NORM_COLS = ["source_system", "source_row_id", "posting_date", "source_account",
             "source_account_name", "project_id", "counterparty", "amount"]


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def _eur_comma(val) -> float:
    """'1.234,56' / '-1.234,56' / '' -> float. Dutch thousands-dot, decimal-comma."""
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _eur_point(val) -> float:
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return 0.0
    return float(s)


def _parse_date(val, fmt: str):
    return datetime.strptime(str(val).strip(), fmt).date()


# --------------------------------------------------------------------------- #
# per-system loaders
# --------------------------------------------------------------------------- #
def load_exact(path: str) -> pd.DataFrame:
    """Exact: comma-delimited, point decimals, US date MM/DD/YYYY, signed AmountDC."""
    df = pd.read_csv(path, dtype=str).fillna("")
    out = pd.DataFrame({
        "source_system": "exact",
        "source_row_id": df["JournalEntryID"],
        "posting_date": df["EntryDate"].map(lambda x: _parse_date(x, "%m/%d/%Y")),
        "source_account": df["GLAccountCode"].str.strip(),
        "source_account_name": df["GLAccountDescription"].str.strip(),
        "project_id": df["CostCenter"].str.strip(),
        "counterparty": df["Relation"].str.strip(),
        "amount": df["AmountDC"].map(_eur_point),
    })
    return out[NORM_COLS]


def load_gilde(path: str) -> pd.DataFrame:
    """Gilde: semicolon, decimal-comma, EU date DD-MM-YYYY, split Debet/Credit.
    No signed amount column -> amount = credit - debet."""
    df = pd.read_csv(path, sep=";", dtype=str).fillna("")
    debet = df["Debet"].map(_eur_comma)
    credit = df["Credit"].map(_eur_comma)
    out = pd.DataFrame({
        "source_system": "gilde",
        "source_row_id": df["Boekstuknr"],
        "posting_date": df["Boekdatum"].map(lambda x: _parse_date(x, "%d-%m-%Y")),
        "source_account": df["Grootboek"].str.strip(),
        "source_account_name": df["Omschrijving"].str.strip(),
        "project_id": df["Project"].str.strip(),
        "counterparty": df["Relatie"].str.strip(),
        "amount": credit - debet,
    })
    return out[NORM_COLS]


def load_yuki(path: str) -> pd.DataFrame:
    """Yuki: comma-delimited, point decimals, ISO date YYYY-MM-DD, signed AmountEUR."""
    df = pd.read_csv(path, dtype=str).fillna("")
    out = pd.DataFrame({
        "source_system": "yuki",
        "source_row_id": df["EntryID"],
        "posting_date": df["Date"].map(lambda x: _parse_date(x, "%Y-%m-%d")),
        "source_account": df["GLAccount"].str.strip(),
        "source_account_name": df["GLDescription"].str.strip(),
        "project_id": df["ProjectCode"].str.strip(),
        "counterparty": df["Contact"].str.strip(),
        "amount": df["AmountEUR"].map(_eur_point),
    })
    return out[NORM_COLS]


def load_snelstart(path: str) -> pd.DataFrame:
    """SnelStart: semicolon, decimal-comma, EU date DD/MM/YYYY, signed BedragEUR."""
    df = pd.read_csv(path, sep=";", dtype=str).fillna("")
    out = pd.DataFrame({
        "source_system": "snelstart",
        "source_row_id": df["Regelnr"],
        "posting_date": df["Datum"].map(lambda x: _parse_date(x, "%d/%m/%Y")),
        "source_account": df["Grootboeknr"].str.strip(),
        "source_account_name": df["Omschrijving"].str.strip(),
        "project_id": df["Projectcode"].str.strip(),
        "counterparty": df["Debiteur"].str.strip(),
        "amount": df["BedragEUR"].map(_eur_comma),
    })
    return out[NORM_COLS]


# Registry: add a 5th system by dropping one loader + filename here. Nothing
# downstream changes (edge-case resilience: new system absorbs cleanly).
LOADERS = {
    "exact":     ("exact_export.csv",     load_exact),
    "gilde":     ("gilde_export.csv",     load_gilde),
    "yuki":      ("yuki_export.csv",      load_yuki),
    "snelstart": ("snelstart_export.csv", load_snelstart),
}


def load_all(raw_dir: str | None = None) -> pd.DataFrame:
    """Load every available system export into one normalised raw frame.
    Systems whose file is missing are skipped with a warning (>=3 required)."""
    raw_dir = raw_dir or config.RAW
    frames = []
    for system, (fname, loader) in LOADERS.items():
        path = os.path.join(raw_dir, fname)
        if not os.path.exists(path):
            print(f"[ingest] WARN: {system} export not found ({fname}); skipping.")
            continue
        frames.append(loader(path))
    if not frames:
        raise FileNotFoundError("No accounting exports found in " + raw_dir)
    return pd.concat(frames, ignore_index=True)
