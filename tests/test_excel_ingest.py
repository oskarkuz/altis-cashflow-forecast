# tests/test_excel_ingest.py
import datetime as dt

from src import excel_ingest


def test_loads_rows_with_vat_gross_up(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-test.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 8, 12), 0.0, 1000.0, "INV1", "Verkoopboek")])
    actuals, recon = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert len(actuals) == 1
    row = actuals.iloc[0]
    assert row["gl_account"] == 8002
    assert row["vat_category"] == "omzet_laag"
    assert row["net_amount"] == 1000.0
    assert row["cash_amount"] == 1090.0          # 9% gross-up
    assert row["iso_year"] == 2026
    assert row["source_excel_row"] == 8          # 1-based excel row of the data line


def test_reverse_charge_not_grossed_up(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-rc.xlsx", "8005 - omzet heffing verlegd",
        [(dt.date(2026, 1, 6), 0.0, 500.0, "INV2", "Verkoopboek")])
    actuals, _ = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert actuals.iloc[0]["cash_amount"] == 500.0   # factor 1.00


def test_reconciliation_passes(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-r.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 3, 2), 0.0, 100.0, "A", "VB"),
         (dt.date(2026, 3, 9), 25.0, 0.0, "B", "VB")])
    _, recon = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    assert len(recon) == 1
    assert recon[0]["reconciles"] is True
    assert recon[0]["net_sum"] == 75.0           # 100 credit - 25 debet
