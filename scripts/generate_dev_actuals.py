"""
generate_dev_actuals.py — DEV-ONLY synthetic stand-in for the real Exact
FinTransactions exports of Dakdekkersbedrijf Peter Ummels.

The real exports are confidential and gitignored; this produces format-identical
.xlsx files (one per revenue GL account) so the app runs end-to-end on any
machine. Revenue follows a realistic ROOFING seasonality — low in winter
(frost/short days), peak spring→autumn — so the seasonal + weather model has
something real to chew on. Deterministic (seed 42). Writes to data/actual_data/.

Run:  python scripts/generate_dev_actuals.py
"""
from __future__ import annotations

import datetime as dt
import os

import numpy as np
from openpyxl import Workbook

SEED = 42
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "actual_data")
rng = np.random.default_rng(SEED)

# account -> (header label, peak weekly NET €, vat note)
ACCOUNTS = {
    8000: ("8000 - Omzet hoog 21%",            55_000, "hoog"),
    8002: ("8002 - Omzet laag 9%",              8_000, "laag"),
    8005: ("8005 - Omzet heffing verlegd",     12_000, "verlegd"),
    8004: ("8004 - Omzet 0% / niet belast",     2_500, "nul"),
}
YEAR_FACTOR = {2023: 1.00, 2024: 1.08, 2025: 1.19, 2026: 1.27}
TODAY = dt.date(2026, 6, 6)
DAGBOEK = "VRK"   # verkoopboek (sales journal)


def seasonal_weight(iso_week: int) -> float:
    """Roofing season curve: winter trough, spring/summer/autumn peak."""
    # smooth bump centred on ~week 28 (mid-July), low in deep winter
    base = 0.45 + 0.85 * np.exp(-((iso_week - 28) ** 2) / (2 * 13.0 ** 2))
    if iso_week <= 6 or iso_week >= 50:      # deep winter extra dip (frost)
        base *= 0.7
    return float(base)


def make_workbook(path, account_header, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Administratie: 82604 - Dakdekkersbedrijf Peter Ummels"])
    ws.append([f"Datum: {TODAY.strftime('%-d %B %Y') if os.name!='nt' else TODAY.isoformat()} door Dev"])
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


def main():
    os.makedirs(OUT, exist_ok=True)
    doc = 200000
    total_net = 0.0
    for account, (header, peak, _note) in ACCOUNTS.items():
        rows = []
        for year, yfac in YEAR_FACTOR.items():
            last_week = 52 if year < 2026 else TODAY.isocalendar().week - 1
            for wkno in range(1, last_week + 1):
                try:
                    invoice_day = dt.date.fromisocalendar(year, wkno, 4)  # Thursday
                except ValueError:
                    continue
                if invoice_day > TODAY:
                    continue
                amt = peak * seasonal_weight(wkno) * yfac * float(rng.normal(1.0, 0.12))
                amt = max(0.0, round(amt, 2))
                if amt < 50:
                    continue
                # 1–2 invoices per week
                n_inv = 1 if rng.random() < 0.6 else 2
                splits = rng.dirichlet(np.ones(n_inv)) * amt
                for part in splits:
                    doc += 1
                    rows.append((invoice_day, 0.0, round(float(part), 2), str(doc)))
                    total_net += float(part)
        path = os.path.join(OUT, f"82604-{account}.xlsx")
        make_workbook(path, header, rows)
        print(f"  82604-{account}.xlsx  {len(rows):>4} rows  net €{sum(r[2] for r in rows):>12,.0f}")
    print(f"Generated {len(ACCOUNTS)} files in {os.path.abspath(OUT)} | total net €{total_net:,.0f}")


if __name__ == "__main__":
    main()
