"""
generate_dev_actuals.py — DEV-ONLY synthetic stand-in for the Altis portfolio's
Exact-style FinTransactions exports.

The real exports are confidential / not on this machine and are gitignored. This
produces format-identical .xlsx files PER PORTFOLIO COMPANY (config.PORTFOLIO),
each in data/actual_data/<id>/, with realistic ROOFING seasonality scaled per
company. Ummels (Brunssum) is the anchor; the others are clearly demo financials
(but each has its own REAL weather by location). Deterministic per-company seed.

Run:  python scripts/generate_dev_actuals.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import config  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "actual_data")
TODAY = config.TODAY
DAGBOEK = "VRK"

# account -> (header label, peak weekly NET € at scale 1.0)
ACCOUNTS = {
    8000: ("8000 - Omzet hoog 21%", 55_000),
    8002: ("8002 - Omzet laag 9%", 8_000),
    8005: ("8005 - Omzet heffing verlegd", 12_000),
    8004: ("8004 - Omzet 0% / niet belast", 2_500),
}
YEAR_FACTOR = {2023: 1.00, 2024: 1.08, 2025: 1.19, 2026: 1.27}


def seasonal_weight(iso_week: int) -> float:
    base = 0.45 + 0.85 * np.exp(-((iso_week - 28) ** 2) / (2 * 13.0 ** 2))
    if iso_week <= 6 or iso_week >= 50:
        base *= 0.7
    return float(base)


def make_workbook(path, company_id, account_header, rows):
    wb = Workbook()
    ws = wb.active
    ws.append([f"Administratie: {company_id} - Altis portfolio (dev)"])
    ws.append([f"Datum: {TODAY.isoformat()} door Dev"])
    ws.append([" Kaart|Grootboekrekening"])
    ws.append([None])
    ws.append(["Criteria"])
    ws.append(["Grootboekrekening", account_header, "Boekjaar", 2026, "Periode", "1 - 12"])
    ws.append(["Nr.", "Per.", "Datum", "Bkst.nr.", "Dagboek", "Debet", "Credit"])
    tot_d = tot_c = 0.0
    for i, (datum, debet, credit, doc_no) in enumerate(rows, start=1):
        ws.append([i, datum.month, datum, doc_no, DAGBOEK, round(debet, 2), round(credit, 2)])
        tot_d += debet
        tot_c += credit
    ws.append(["Totaal", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    ws.append(["Eindsaldo", None, None, None, None, round(tot_d, 2), round(tot_c, 2)])
    wb.save(path)


def gen_company(company):
    rng = np.random.default_rng(company["seed"])
    scale = company["scale"]
    folder = os.path.join(OUT, company["id"])
    os.makedirs(folder, exist_ok=True)
    doc, total = 200000, 0.0
    for account, (header, peak) in ACCOUNTS.items():
        rows = []
        for year, yfac in YEAR_FACTOR.items():
            last_week = 52 if year < 2026 else TODAY.isocalendar().week - 1
            for wkno in range(1, last_week + 1):
                try:
                    day = dt.date.fromisocalendar(year, wkno, 4)
                except ValueError:
                    continue
                if day > TODAY:
                    continue
                amt = peak * scale * seasonal_weight(wkno) * yfac * float(rng.normal(1.0, 0.12))
                amt = max(0.0, round(amt, 2))
                if amt < 50:
                    continue
                splits = rng.dirichlet(np.ones(1 if rng.random() < 0.6 else 2)) * amt
                for part in splits:
                    doc += 1
                    rows.append((day, 0.0, round(float(part), 2), str(doc)))
                    total += float(part)
        prefix = "82604" if company["id"] == "ummels" else company["id"]
        make_workbook(os.path.join(folder, f"{prefix}-{account}.xlsx"),
                      company["id"], header, rows)
    return total


def main():
    os.makedirs(OUT, exist_ok=True)
    for c in config.PORTFOLIO:
        total = gen_company(c)
        tag = "REAL-format" if c["real"] else "demo"
        print(f"  {c['id']:<11} {c['city']:<11} [{tag}]  net €{total:>12,.0f}")
    print(f"Generated {len(config.PORTFOLIO)} companies in {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
