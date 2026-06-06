# tests/test_audit.py
import datetime as dt

from src import audit, excel_ingest, forecast
from tests.conftest import make_actuals


def _rec(date, net, eid):
    return {"date": date, "gl_account": 8002, "vat_category": "omzet_laag",
            "vat_rate": 0.09, "net_amount": net,
            "cash_amount": round(net * 1.09, 2), "event_id": eid}


def test_drill_down_filters_week_and_category():
    a = make_actuals([_rec(dt.date(2025, 6, 9), 100, "s1")])
    events, _ = forecast.build_forecast(
        a, start_date=dt.date(2026, 6, 8), n_weeks=13, payment_terms_days=0,
        seasonal_years=[2025])
    one = audit.drill_down(events, week=1, vat_category="omzet_laag")
    assert len(one) == 1 and one.iloc[0]["week"] == 1


def test_trace_seed_rows_resolves_actual_rows():
    a = make_actuals([_rec(dt.date(2025, 6, 9), 100, "s1"),
                      _rec(dt.date(2025, 6, 10), 200, "s2")])
    events, _ = forecast.build_forecast(
        a, start_date=dt.date(2026, 6, 8), n_weeks=13, payment_terms_days=0,
        seasonal_years=[2025])
    ev = audit.drill_down(events, week=1, vat_category="omzet_laag").iloc[0]
    seeds = audit.trace_seed_rows(ev, a)
    assert set(seeds["event_id"]) == {"s1", "s2"}


def test_read_excel_row_returns_literal_cells(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-z.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 4, 6), 0.0, 777.0, "INV9", "Verkoopboek")])
    actuals, _ = excel_ingest.load_revenue_actuals(fintransactions_factory.glob)
    row = actuals.iloc[0]
    raw = audit.read_excel_row(row["source_file"], int(row["source_excel_row"]),
                               fintransactions_factory.glob)
    assert raw["raw_file"] == row["source_file"]
    assert 777.0 in raw["row"].values()


def test_read_excel_row_missing_file_returns_none(fintransactions_factory):
    raw = audit.read_excel_row("does-not-exist.xlsx", 8, fintransactions_factory.glob)
    assert raw["row"] is None


def test_read_excel_row_out_of_range_yields_none_cells(fintransactions_factory):
    fintransactions_factory(
        "82604-2026-oor.xlsx", "8002 - Omzet belast 9%",
        [(dt.date(2026, 4, 6), 0.0, 100.0, "INV1", "Verkoopboek")])
    raw = audit.read_excel_row("82604-2026-oor.xlsx", 9999,
                               fintransactions_factory.glob)
    assert all(v is None for v in raw["row"].values())


def test_trace_seed_rows_missing_key_returns_empty():
    a = make_actuals([_rec(dt.date(2025, 6, 9), 100, "s1")])
    seeds = audit.trace_seed_rows({"week": 1}, a)
    assert len(seeds) == 0
