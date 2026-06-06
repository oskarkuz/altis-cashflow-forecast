"""Shared test fixtures: build minimal Exact-FinTransactions .xlsx files that
match the real layout, and a helper to build an actuals DataFrame directly."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from openpyxl import Workbook


def make_fintransactions_xlsx(path, account_header, rows):
    """Write one Exact-FinTransactions-format workbook.

    account_header: e.g. "8002 - Omzet belast 9%"
    rows: list of (datum: date, debet: float, credit: float, doc_no: str, dagboek: str)
    Adds a trailing Eindsaldo row = sum(credit) - sum(debet).
    Layout mirrors the real files: a 'Grootboekrekening' criteria row carrying
    the account, a 'Nr.' data header, data rows
    [Nr, Per, Datum, Bkst.nr, Dagboek, Debet, Credit], then 'Eindsaldo'.
    """
    wb = Workbook()
    ws = wb.active
    ws.append(["Administratie: 82604 - Dakdekkersbedrijf Peter Ummels"])
    ws.append(["Datum: 4 juni 2026 door Test"])
    ws.append([" Kaart|Grootboekrekening"])
    ws.append([None])
    ws.append(["Criteria"])
    ws.append(["Grootboekrekening", account_header, "Boekjaar", 2026, "Periode", "1 - 12"])
    ws.append(["Nr.", "Per.", "Datum", "Bkst.nr.", "Dagboek", "Debet", "Credit"])
    tot_d = tot_c = 0.0
    for i, (datum, debet, credit, doc_no, dagboek) in enumerate(rows, start=1):
        ws.append([i, datum.month, datum, doc_no, dagboek, debet, credit])
        tot_d += debet
        tot_c += credit
    ws.append(["Totaal", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    ws.append(["Eindsaldo", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    wb.save(path)
    return str(path)


@pytest.fixture
def fintransactions_factory(tmp_path):
    """Return a builder that drops .xlsx files into a tmp dir and yields a glob
    matching them (for excel_ingest / pipeline)."""
    made = []

    def _make(name, account_header, rows):
        p = tmp_path / name
        made.append(make_fintransactions_xlsx(p, account_header, rows))
        return p

    _make.glob = str(tmp_path / "82604-*.xlsx")
    return _make


def make_actuals(records):
    """Build a revenue_actuals-shaped DataFrame directly (no Excel) for forecast/
    audit unit tests. records: list of dicts with at least
    date, gl_account, vat_category, vat_rate, net_amount, cash_amount, event_id."""
    df = pd.DataFrame(records)
    iso = df["date"].map(lambda d: d.isocalendar())
    df["iso_year"] = iso.map(lambda c: c[0])
    df["iso_week"] = iso.map(lambda c: c[1])
    return df
