"""Altis — Dakdekkersbedrijf Peter Ummels: honest 13-week revenue cash-flow forecast.

Single company, revenue-only. Two views: Forecast (seasonal projection) and
Actuals & history. Every figure is a live aggregation of forecast_events /
revenue_actuals and traces to its source Excel cell. No weather/covenant/WIP/
scenarios — the source data does not contain them.
"""
from __future__ import annotations

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import audit, config, pipeline  # noqa: E402

st.set_page_config(page_title="Altis — Dakdekkersbedrijf Cash-Flow",
                   page_icon="💶", layout="wide")

CAT_LABELS = {
    "omzet_hoog": "Omzet hoog (21%)", "omzet_laag": "Omzet laag (9%)",
    "omzet_nul": "Omzet 0%", "omzet_verlegd": "Omzet verlegd (reverse charge)",
    "unmapped": "Unmapped",
}
CAT_COLORS = {
    "omzet_verlegd": "#2c7fb8", "omzet_hoog": "#fdae61",
    "omzet_laag": "#7fcdbb", "omzet_nul": "#c2a5cf", "unmapped": "#d73027",
}


def euro(x):
    return f"€{x:,.0f}"


@st.cache_data(show_spinner="Parsing the Exact exports and building the forecast…")
def load_bundle():
    return pipeline.run()


bundle = load_bundle()
actuals = bundle["revenue_actuals"]
events = bundle["forecast_events"]
rep = bundle["recon_report"]

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("Altis Groep")
st.sidebar.caption(f"13-week revenue cash-flow forecast · {bundle['company']}")
view = st.sidebar.radio("**View**", ["Forecast", "Actuals & history"], index=0)

st.sidebar.divider()
st.sidebar.markdown("**Reconciliation**")
flag = "✅" if rep["all_pass"] else "⚠️"
st.sidebar.write(f"- {flag} {rep['n_files']} files, "
                 f"{'all reconcile' if rep['all_pass'] else 'SOME FAIL'}")
st.sidebar.write(f"- Σ net reconciled: **{euro(rep['total_reconciled'])}**")
st.sidebar.caption(
    "Real Exact FinTransactions exports (revenue/omzet accounts only). The forecast "
    "is **seasonal**: each forward week = the mean of that ISO-week's revenue across "
    f"{config.SEASONAL_YEARS}, scaled by a clamped YoY factor, shifted by a "
    f"{config.PAYMENT_TERMS_DAYS}-day payment-lag assumption.")
st.sidebar.info(
    "**Not modelled** (no source data): weather, covenant headroom, WIP/project "
    "risk, opening cash, supplier/subcontractor costs.")


def cat_chart(long_df, x, y, title_y):
    return alt.Chart(long_df).mark_bar().encode(
        x=alt.X(f"{x}:O", title="Week"),
        y=alt.Y(f"{y}:Q", title=title_y, stack="zero"),
        color=alt.Color("vat_category:N",
                        scale=alt.Scale(domain=list(CAT_COLORS),
                                        range=list(CAT_COLORS.values())),
                        legend=alt.Legend(title="VAT category")),
        tooltip=["week:O", "vat_category:N", alt.Tooltip(f"{y}:Q", format=",.0f")])


def audit_panel():
    st.markdown("#### 🔎 Audit drill-down — trace a forecast figure to its Excel cell")
    cats = ["ALL"] + sorted(events["vat_category"].unique())
    c1, c2 = st.columns(2)
    wk = c1.selectbox("Week", list(range(1, config.N_WEEKS + 1)), key="aud_wk")
    cat = c2.selectbox("VAT category", cats, key="aud_cat")
    fil = audit.drill_down(events, week=int(wk),
                           vat_category=None if cat == "ALL" else cat)
    st.metric(f"Forecast cash — week {wk}, {cat}", euro(fil["amount"].sum()))
    show = fil.copy()
    show["assumptions"] = show["assumptions"].map(lambda a: "; ".join(a))
    show["seeds"] = show["seed_event_ids"].map(len)
    st.dataframe(show[["event_id", "week", "vat_category", "amount",
                       "invoice_iso_week", "seeds", "assumptions"]],
                 use_container_width=True, hide_index=True)

    seeded = fil[fil["seed_event_ids"].map(len) > 0]
    if len(seeded):
        st.markdown("**Trace one forecast event → its seeding actuals → a raw Excel row:**")
        ev_id = st.selectbox("forecast event", seeded["event_id"].tolist(), key="aud_ev")
        ev = seeded[seeded["event_id"] == ev_id].iloc[0]
        seeds = audit.trace_seed_rows(ev, actuals)
        st.caption(f"{len(seeds)} historical rows seed this forecast cell:")
        st.dataframe(seeds[["event_id", "date", "vat_category", "net_amount",
                            "cash_amount", "doc_no", "source_file",
                            "source_excel_row"]],
                     use_container_width=True, hide_index=True)
        if len(seeds):
            pick = st.selectbox("trace to Excel row", seeds["event_id"].tolist(),
                                key="aud_seed")
            s = seeds[seeds["event_id"] == pick].iloc[0]
            raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
            st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
            st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


# --------------------------------------------------------------------------- #
# FORECAST VIEW
# --------------------------------------------------------------------------- #
def forecast_view():
    k = bundle["kpis"]
    st.title("13-Week Revenue Cash-Flow Forecast")
    c1, c2, c3 = st.columns(3)
    c1.metric("Forecast cash (13 wk)", euro(k["forecast_total"]))
    c2.metric("Avg / week", euro(k["avg_weekly"]))
    c3.metric("YoY growth (applied)", f"{k['yoy_pct']:+.1f}%")

    st.subheader("Forecast cash by week and VAT category")
    wf = bundle["weekly_forecast"]
    long = wf.reset_index(names="week").melt("week", var_name="vat_category",
                                             value_name="amount")
    st.altair_chart(cat_chart(long, "week", "amount", "Forecast cash (€)"),
                    use_container_width=True)

    tbl = wf.copy()
    tbl["TOTAL"] = tbl.sum(axis=1)
    tbl.loc["TOTAL"] = tbl.sum()
    st.dataframe(tbl.style.format("{:,.0f}"), use_container_width=True)

    with st.expander("📐 Seasonal basis — how each week was derived", expanded=False):
        st.caption("Each forward week maps to an invoice ISO-week (cash date minus the "
                   "payment-lag assumption); the forecast = mean of that ISO-week's "
                   "revenue across prior years × the clamped YoY factor.")
        b = bundle["seasonal_basis"].copy()
        b["seed_years"] = b["seed_years"].map(lambda y: ", ".join(map(str, y)))
        st.dataframe(b[["week", "cash_date", "invoice_iso_week", "vat_category",
                        "base_mean", "yoy_factor", "amount", "n_seed_rows",
                        "seed_years"]].style.format(
            {"base_mean": "{:,.0f}", "amount": "{:,.0f}", "yoy_factor": "{:.2f}"}),
            use_container_width=True, hide_index=True)

    st.divider()
    audit_panel()


# --------------------------------------------------------------------------- #
# ACTUALS & HISTORY VIEW
# --------------------------------------------------------------------------- #
def actuals_view():
    st.title("Actuals & History — Reconciled Revenue")
    a = actuals.copy()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total revenue (cash, all years)", euro(a["cash_amount"].sum()))
    c2.metric("Ledger lines", f"{len(a):,}")
    c3.metric("Years", f"{a['iso_year'].min()}–{a['iso_year'].max()}")

    st.subheader("Weekly revenue by year")
    wk = (a.groupby(["iso_year", "iso_week"], as_index=False)["cash_amount"].sum())
    line = alt.Chart(wk).mark_line().encode(
        x=alt.X("iso_week:Q", title="ISO week"),
        y=alt.Y("cash_amount:Q", title="Revenue cash (€)"),
        color=alt.Color("iso_year:N", title="Year"),
        tooltip=["iso_year:N", "iso_week:Q",
                 alt.Tooltip("cash_amount:Q", format=",.0f")])
    st.altair_chart(line, use_container_width=True)

    st.subheader("Reconciliation by file")
    rec = pd.DataFrame(rep["files"])
    st.dataframe(rec.style.format({"net_sum": "{:,.2f}", "eindsaldo": "{:,.2f}"}),
                 use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 🔎 Trace any actual posting to its Excel cell")
    yr = st.selectbox("Year", sorted(a["iso_year"].unique()), key="act_yr")
    sub = a[a["iso_year"] == yr].head(500)
    st.dataframe(sub[["event_id", "date", "vat_category", "net_amount",
                      "cash_amount", "doc_no", "source_file", "source_excel_row"]],
                 use_container_width=True, hide_index=True)
    pick = st.selectbox("posting", sub["event_id"].tolist(), key="act_ev")
    s = sub[sub["event_id"] == pick].iloc[0]
    raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
    st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
    st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


if view == "Forecast":
    forecast_view()
else:
    actuals_view()
