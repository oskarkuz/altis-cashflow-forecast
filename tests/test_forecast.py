# tests/test_forecast.py
import datetime as dt

from src import forecast
from tests.conftest import make_actuals


def _rec(date, cat, net, rate, eid):
    return {"date": date, "gl_account": 8002, "vat_category": cat,
            "vat_rate": rate, "net_amount": net,
            "cash_amount": round(net * (1 + rate), 2), "event_id": eid}


def test_weekly_actuals_aggregates_by_iso_week_year_category():
    a = make_actuals([
        _rec(dt.date(2025, 3, 3), "omzet_laag", 100, 0.09, "e1"),
        _rec(dt.date(2025, 3, 4), "omzet_laag", 200, 0.09, "e2"),  # same ISO week
        _rec(dt.date(2025, 6, 2), "omzet_laag", 50, 0.09, "e3"),
    ])
    wk = forecast.weekly_actuals(a)
    march = wk[(wk["iso_year"] == 2025) & (wk["iso_week"] == 10)]
    assert march["cash"].iloc[0] == round(300 * 1.09, 2)


def test_yoy_factor_is_clamped():
    a = make_actuals([
        _rec(dt.date(2025, 1, 6), "omzet_laag", 100, 0.0, "p"),    # iso wk 2
        _rec(dt.date(2026, 1, 5), "omzet_laag", 1000, 0.0, "c"),   # iso wk 2, 10x
    ])
    # raw 10x -> clamped to upper bound 2.0
    assert forecast.yoy_factor(a, current_year=2026, prior_year=2025,
                               clamp=(0.5, 2.0)) == 2.0


def test_build_forecast_uses_prior_year_same_week_mean_times_yoy():
    # Two prior years, same ISO week as the forecast's first invoice week.
    start = dt.date(2026, 6, 8)              # cash week 1
    lag = 0                                  # invoice week == cash week
    iso_wk = start.isocalendar().week        # 24
    d24_2024 = dt.date.fromisocalendar(2024, iso_wk, 1)
    d24_2025 = dt.date.fromisocalendar(2025, iso_wk, 1)
    a = make_actuals([
        _rec(d24_2024, "omzet_laag", 1000, 0.0, "y24"),
        _rec(d24_2025, "omzet_laag", 3000, 0.0, "y25"),
    ])
    events, basis = forecast.build_forecast(
        a, start_date=start, n_weeks=13, payment_terms_days=lag,
        seasonal_years=[2024, 2025], yoy_clamp=(0.5, 2.0))
    wk1 = events[(events["week"] == 1) & (events["vat_category"] == "omzet_laag")].iloc[0]
    # mean(1000, 3000) = 2000 ; yoy = 1.0 (no 2026 actuals) -> 2000
    assert wk1["amount"] == 2000.0
    assert set(wk1["seed_event_ids"]) == {"y24", "y25"}
    assert len(events[events["vat_category"] == "omzet_laag"]) == 13


def test_empty_forward_week_forecasts_zero_with_tag():
    start = dt.date(2026, 6, 8)
    a = make_actuals([_rec(dt.date(2024, 1, 8), "omzet_laag", 100, 0.0, "x")])  # wk 2 only
    events, _ = forecast.build_forecast(
        a, start_date=start, n_weeks=1, payment_terms_days=0,
        seasonal_years=[2024], yoy_clamp=(0.5, 2.0))
    row = events.iloc[0]
    assert row["amount"] == 0.0
    assert any("no seasonal base" in t for t in row["assumptions"])
