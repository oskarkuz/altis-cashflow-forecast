"""Dakdekkersbedrijf Peter Ummels — weather-aware 13-week revenue cash-flow forecast.

Single roofing company, revenue-only, built on REAL Exact FinTransactions exports
+ REAL Open-Meteo weather (historical climatology + SEAS5 seasonal forecast).
Four role views (Owner / Operations / PE Board / Bookkeeper). Every figure is a
live aggregation that traces to its source Excel cell. Brand palette from
dakdekkersbedrijf-ummels.nl.
"""
from __future__ import annotations

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import audit, config, pipeline  # noqa: E402

st.set_page_config(page_title="Peter Ummels — Cash-Flow Forecast",
                   page_icon="🏠", layout="wide")

# --------------------------------------------------------------------------- #
# Brand palette (Ummels) + floating-dashboard CSS
# --------------------------------------------------------------------------- #
RED, BLUE, NAVY = "#ED1C24", "#005CA8", "#002E54"
SKY, GREY, AMBER = "#7FB0DD", "#8A97A6", "#E8920C"
CAT_LABELS = {
    "omzet_hoog": "Revenue 21%", "omzet_laag": "Revenue 9%",
    "omzet_nul": "Revenue 0%", "omzet_verlegd": "Reverse-charge", "unmapped": "Unmapped",
}
CAT_COLORS = {"omzet_hoog": BLUE, "omzet_laag": SKY, "omzet_verlegd": NAVY,
              "omzet_nul": "#B9C4CF", "unmapped": RED}

st.markdown("""
<style>
.block-container {padding-top: 1.1rem; max-width: 1180px;}
.ummels-hero {background: linear-gradient(100deg,#002E54 0%,#005CA8 72%);
  color:#fff; border-radius:16px; padding:16px 24px; margin-bottom:14px;
  box-shadow:0 8px 24px rgba(0,46,84,.18); display:flex; align-items:center;
  justify-content:space-between;}
.ummels-hero h1{color:#fff; font-size:1.45rem; margin:0; font-weight:800;}
.ummels-hero .sub{opacity:.85; font-size:.88rem; margin-top:2px;}
.ummels-chip{background:#ED1C24; padding:5px 14px; border-radius:20px;
  font-weight:700; font-size:.8rem; letter-spacing:.02em;}
div[data-testid="stMetric"]{background:#fff; border:1px solid #e6ebf1;
  border-left:5px solid #ED1C24; border-radius:14px; padding:14px 18px 10px;
  box-shadow:0 6px 18px rgba(0,46,84,.07);}
div[data-testid="stMetricLabel"] p{font-size:.8rem; color:#5a6b7e; font-weight:600;}
div[data-testid="stMetricValue"]{color:#0F2540; font-weight:800; font-size:1.6rem;}
div[data-testid="stVerticalBlockBorderWrapper"]{box-shadow:0 4px 16px rgba(0,46,84,.06);
  border-radius:14px;}
.fc-warn{background:#FFF4E5; border:1px solid #F3C77A; border-left:5px solid #E8920C;
  border-radius:12px; padding:10px 16px; font-size:.9rem; color:#6b4e16; margin:.3rem 0 1rem;}
.note{color:#5a6b7e; font-size:.85rem;}
h1,h2,h3{color:#0F2540;}
</style>
""", unsafe_allow_html=True)


def euro(x):
    return f"€{x:,.0f}"


@st.cache_data(show_spinner="Reading Exact exports, weather & building the forecast…")
def load_bundle():
    return pipeline.run()


bundle = load_bundle()
actuals = bundle["revenue_actuals"]
events = bundle["forecast_events"]
basis = bundle["seasonal_basis"]
rep = bundle["recon_report"]
wfac = bundle.get("weather_factors", {})
wsum = bundle.get("weather_summary", {})

ROLES = {
    "Owner": "Owner / Directie",
    "Operations": "Operations & Weather",
    "PE Board": "PE Board",
    "Bookkeeper": "Bookkeeper",
}

# --------------------------------------------------------------------------- #
# Sidebar — role switcher + trust signals
# --------------------------------------------------------------------------- #
st.sidebar.markdown(f"### 🏠 {bundle['company'].split(' ',1)[-1] if False else 'Peter Ummels'}")
st.sidebar.caption(f"{bundle['company']} · {bundle['location']}")
role = st.sidebar.radio("**Who are you?**", list(ROLES), index=0,
                        format_func=lambda r: ROLES[r])

st.sidebar.divider()
flag = "✅" if rep["all_pass"] else "⚠️"
st.sidebar.markdown("**Data trust**")
st.sidebar.write(f"- {flag} {rep['n_files']} Exact files {'all reconcile' if rep['all_pass'] else 'SOME FAIL'}")
st.sidebar.write(f"- Σ revenue reconciled: **{euro(rep['total_reconciled'])}**")
if wsum:
    st.sidebar.write(f"- 🌦️ Weather: SEAS5 + {actuals['iso_year'].min()}–{actuals['iso_year'].max()} history")
st.sidebar.caption("Real Exact FinTransactions + real Open-Meteo weather. "
                   "Every figure traces to a source Excel cell.")

# brand header
st.markdown(f"""<div class="ummels-hero">
  <div><h1>Dakdekkersbedrijf Peter Ummels</h1>
  <div class="sub">13-week revenue cash-flow forecast · {bundle['location']} · weather-aware</div></div>
  <div class="ummels-chip">{ROLES[role].upper()}</div>
</div>""", unsafe_allow_html=True)

FC_WARN = ('<div class="fc-warn">⚠️ <b>This is a forecast — an estimate, not a guarantee.</b> '
           'It is built from 3 years of invoice history and the SEAS5 weather outlook, and it '
           'will change as new sales and weather data arrive. Treat it as a planning range.</div>')


def weather_weekly_df():
    """Per-week weather: factor, € impact, workable now vs typical."""
    if basis.empty or not wfac:
        return pd.DataFrame()
    g = basis.groupby("week").agg(amount=("amount", "sum"),
                                  pre=("amount_pre_weather", "sum")).reset_index()
    g["delta"] = (g["amount"] - g["pre"]).round(0)
    g["factor"] = g["week"].map(lambda w: wfac.get(w, {}).get("factor", 1.0))
    g["forward_workable"] = g["week"].map(lambda w: wfac.get(w, {}).get("forward_workable"))
    g["typical_workable"] = g["week"].map(lambda w: wfac.get(w, {}).get("typical_workable"))
    g["lost_days"] = g["week"].map(lambda w: wfac.get(w, {}).get("lost_days"))
    g["outlook"] = g["factor"].map(lambda f: "Drier than usual" if f > 1.02
                                   else ("Wetter than usual" if f < 0.98 else "Normal"))
    return g


def weekly_total_chart():
    """Clean weekly expected-revenue bars (brand) with weather tooltip."""
    g = basis.groupby("week").agg(amount=("amount", "sum"),
                                  pre=("amount_pre_weather", "sum")).reset_index()
    g["date"] = g["week"].map(lambda w: events[events["week"] == w]["cash_date"].iloc[0])
    bars = alt.Chart(g).mark_bar(color=BLUE, cornerRadiusTopLeft=4,
                                 cornerRadiusTopRight=4).encode(
        x=alt.X("week:O", title="Forecast week"),
        y=alt.Y("amount:Q", title="Expected revenue (€)"),
        tooltip=[alt.Tooltip("week:O", title="Week"),
                 alt.Tooltip("date:T", title="Week of"),
                 alt.Tooltip("amount:Q", title="Expected €", format=",.0f"),
                 alt.Tooltip("pre:Q", title="Before weather €", format=",.0f")])
    return bars.properties(height=300)


# --------------------------------------------------------------------------- #
# Shared audit panel (trace to Excel cell)
# --------------------------------------------------------------------------- #
def audit_panel():
    with st.expander("🔎 Trace any number back to the source Excel cell", expanded=False):
        cats = ["ALL"] + sorted(events["vat_category"].unique())
        c1, c2 = st.columns(2)
        wk = c1.selectbox("Week", list(range(1, config.N_WEEKS + 1)), key="aud_wk")
        cat = c2.selectbox("Revenue type", cats, key="aud_cat",
                           format_func=lambda c: CAT_LABELS.get(c, c))
        fil = audit.drill_down(events, week=int(wk),
                               vat_category=None if cat == "ALL" else cat)
        st.metric(f"Forecast — week {wk}", euro(fil["amount"].sum()))
        seeded = fil[fil["seed_event_ids"].map(len) > 0]
        if len(seeded):
            ev_id = st.selectbox("Pick a forecast cell", seeded["event_id"].tolist(),
                                 key="aud_ev")
            ev = seeded[seeded["event_id"] == ev_id].iloc[0]
            st.caption("Assumptions: " + " · ".join(ev["assumptions"]))
            seeds = audit.trace_seed_rows(ev, actuals)
            st.caption(f"Seeded by {len(seeds)} historical invoices:")
            st.dataframe(seeds[["date", "vat_category", "cash_amount", "doc_no",
                                "source_file", "source_excel_row"]],
                         use_container_width=True, hide_index=True)
            if len(seeds):
                pick = st.selectbox("Trace one to its Excel row", seeds["event_id"].tolist(),
                                    key="aud_seed")
                s = seeds[seeds["event_id"] == pick].iloc[0]
                raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
                st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
                st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


# --------------------------------------------------------------------------- #
# OWNER VIEW
# --------------------------------------------------------------------------- #
def owner_view():
    st.toast("This is a forecast — an estimate, not a guarantee.", icon="⚠️")
    k = bundle["kpis"]
    delta = bundle.get("weather_revenue_delta", 0.0)
    pre = bundle.get("weather_pre_total", 0.0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Expected revenue · next 13 weeks", euro(k["forecast_total"]))
    c2.metric("Average per week", euro(k["avg_weekly"]))
    c3.metric("vs same period last year", f"{k['yoy_pct']:+.1f}%")
    c4.metric("Weather effect", f"{euro(delta)}",
              delta=f"{(delta/pre*100 if pre else 0):+.1f}% vs normal")

    st.markdown(FC_WARN, unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("What we expect to collect, week by week")
        st.altair_chart(weekly_total_chart(), use_container_width=True)
        st.markdown('<span class="note">Bars are the expected cash from roofing invoices, '
                    'after a payment-lag and a weather adjustment. Hover to compare with the '
                    '“before weather” figure.</span>', unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("Simple weekly plan")
        g = weather_weekly_df()
        if not g.empty:
            show = g.copy()
            show["Week of"] = show["week"].map(
                lambda w: events[events["week"] == w]["cash_date"].iloc[0])
            show["Weather"] = show["factor"].map(lambda f: f"{(f-1)*100:+.0f}%")
            disp = show[["week", "Week of", "amount", "Weather", "outlook"]].rename(
                columns={"week": "Week", "amount": "Expected € ", "outlook": "Outlook"})
            st.dataframe(disp.style.format({"Expected € ": "{:,.0f}", "Week of": "{:%d %b}"}),
                         use_container_width=True, hide_index=True)

    with st.expander("📐 How is this built? (seasonal history × growth × weather)"):
        b = basis.copy()
        b["seed_years"] = b["seed_years"].map(lambda y: ", ".join(map(str, y)))
        b["type"] = b["vat_category"].map(lambda c: CAT_LABELS.get(c, c))
        st.dataframe(b[["week", "type", "base_mean", "yoy_factor", "weather_factor",
                        "amount", "n_seed_rows"]].rename(columns={
            "base_mean": "history avg €", "yoy_factor": "growth", "weather_factor": "weather",
            "amount": "forecast €", "n_seed_rows": "# history rows"}).style.format(
            {"history avg €": "{:,.0f}", "forecast €": "{:,.0f}",
             "growth": "{:.2f}", "weather": "{:.2f}"}),
            use_container_width=True, hide_index=True)
    audit_panel()


# --------------------------------------------------------------------------- #
# OPERATIONS & WEATHER VIEW
# --------------------------------------------------------------------------- #
def operations_view():
    st.toast("Weather outlook from SEAS5 — a forecast, it updates monthly.", icon="🌦️")
    c1, c2, c3, c4 = st.columns(4)
    mean_f = wsum.get("mean_factor", 1.0)
    c1.metric("Weather effect on revenue", f"{(mean_f-1)*100:+.1f}%",
              help="Average across the 13 weeks vs the seasonal norm")
    c2.metric("Expected lost roofing days", f"{wsum.get('expected_lost_days', 0):.0f}",
              help="Across the 13-week window (rain/frost)")
    c3.metric("Weeks wetter than normal", wsum.get("weeks_wetter", 0))
    c4.metric("Weeks drier than normal", wsum.get("weeks_drier", 0))

    st.markdown('<div class="fc-warn">🌦️ Weather is a <b>seasonal forecast</b> (ECMWF SEAS5, '
                f'51-member ensemble) for {bundle["location"]}, compared to the '
                f'{actuals["iso_year"].min()}–{actuals["iso_year"].max()} climatology. It is an '
                'outlook, not a daily forecast — it shifts the revenue estimate, it does not fix it.</div>',
                unsafe_allow_html=True)

    g = weather_weekly_df()
    with st.container(border=True):
        st.subheader("How weather nudges each week's revenue")
        if not g.empty:
            ch = alt.Chart(g).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("week:O", title="Forecast week"),
                y=alt.Y("delta:Q", title="Revenue moved by weather (€)"),
                color=alt.Color("outlook:N", scale=alt.Scale(
                    domain=["Wetter than usual", "Normal", "Drier than usual"],
                    range=[RED, GREY, "#1a9850"]), legend=alt.Legend(title="Outlook")),
                tooltip=[alt.Tooltip("week:O", title="Week"),
                         alt.Tooltip("delta:Q", title="€ moved", format=",.0f"),
                         alt.Tooltip("factor:Q", title="factor", format=".2f"),
                         alt.Tooltip("forward_workable:Q", title="workable now"),
                         alt.Tooltip("typical_workable:Q", title="workable typical")])
            st.altair_chart(ch.properties(height=280), use_container_width=True)
            st.markdown('<span class="note">Green = drier than the seasonal norm (more roofing '
                        'days → revenue pulled up). Red = wetter (work and cash pushed down).</span>',
                        unsafe_allow_html=True)

    fwd = bundle.get("weather_forward")
    if fwd is not None and len(fwd):
        with st.container(border=True):
            st.subheader("Daily outlook — rain & workable roofing days")
            f = fwd.copy()
            f["workable_pct"] = (f["workable_frac"] * 100).round(0)
            rain = alt.Chart(f).mark_bar(color=SKY, opacity=.7).encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("precip:Q", title="Rain (mm/day)"),
                tooltip=[alt.Tooltip("date:T"), alt.Tooltip("precip:Q", format=".1f")])
            work = alt.Chart(f).mark_line(color=RED, strokeWidth=2).encode(
                x="date:T", y=alt.Y("workable_pct:Q", title="Workable chance (%)"),
                tooltip=[alt.Tooltip("date:T"),
                         alt.Tooltip("workable_pct:Q", title="workable %")])
            st.altair_chart(alt.layer(rain, work).resolve_scale(y="independent")
                            .properties(height=260), use_container_width=True)

    with st.expander("📅 Week-by-week weather detail"):
        if not g.empty:
            d = g.copy()
            d["workable now"] = (d["forward_workable"] * 100).round(0)
            d["typical"] = (d["typical_workable"] * 100).round(0)
            st.dataframe(d[["week", "workable now", "typical", "lost_days", "factor",
                            "delta", "outlook"]].rename(columns={
                "week": "Week", "lost_days": "exp. lost days", "delta": "€ moved"}).style.format(
                {"€ moved": "{:,.0f}", "factor": "{:.2f}", "workable now": "{:.0f}%",
                 "typical": "{:.0f}%", "exp. lost days": "{:.1f}"}),
                use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# PE BOARD VIEW
# --------------------------------------------------------------------------- #
def pe_board_view():
    k = bundle["kpis"]
    a = actuals
    by_year = a.groupby("iso_year")["cash_amount"].sum()
    full_years = [y for y in by_year.index if y < a["iso_year"].max()]
    run_rate = by_year[full_years].mean() if full_years else by_year.mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Annual run-rate (revenue)", euro(run_rate))
    c2.metric("Forecast · next 13 weeks", euro(k["forecast_total"]))
    c3.metric("Growth vs last year", f"{k['yoy_pct']:+.1f}%")
    c4.metric("Weather sensitivity", f"{wsum.get('expected_lost_days', 0):.0f} lost days",
              help="Roofing revenue at risk from rain/frost over the window")

    st.markdown('<span class="note">Portfolio company 2 · Dakdekkersbedrijf Peter Ummels · '
                'Exact Online (ID 82604). Revenue-only view; costs/margin not in source data.</span>',
                unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("Revenue trajectory")
        yr = by_year.reset_index().rename(columns={"cash_amount": "revenue"})
        yr["kind"] = yr["iso_year"].map(lambda y: "Year-to-date" if y == a["iso_year"].max()
                                        else "Full year")
        bar = alt.Chart(yr).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("iso_year:O", title="Year"),
            y=alt.Y("revenue:Q", title="Revenue (€)"),
            color=alt.Color("kind:N", scale=alt.Scale(
                domain=["Full year", "Year-to-date"], range=[BLUE, SKY]),
                legend=alt.Legend(title=None)),
            tooltip=["iso_year:O", alt.Tooltip("revenue:Q", format=",.0f"), "kind:N"])
        st.altair_chart(bar.properties(height=260), use_container_width=True)

    with st.container(border=True):
        st.subheader("Seasonality — weekly revenue by year")
        wk = a.groupby(["iso_year", "iso_week"], as_index=False)["cash_amount"].sum()
        line = alt.Chart(wk).mark_line(strokeWidth=2).encode(
            x=alt.X("iso_week:Q", title="Week of year"),
            y=alt.Y("cash_amount:Q", title="Revenue (€)"),
            color=alt.Color("iso_year:N", title="Year",
                            scale=alt.Scale(scheme="blues")),
            tooltip=["iso_year:N", "iso_week:Q", alt.Tooltip("cash_amount:Q", format=",.0f")])
        st.altair_chart(line.properties(height=260), use_container_width=True)
        st.markdown('<span class="note">Classic roofing seasonality: a summer peak, a winter '
                    'trough. The 13-week forecast sits on this curve, nudged by the weather outlook.</span>',
                    unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# BOOKKEEPER VIEW
# --------------------------------------------------------------------------- #
def bookkeeper_view():
    a = actuals
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue reconciled", euro(rep["total_reconciled"]))
    c2.metric("Exact files", rep["n_files"])
    c3.metric("Ledger lines", f"{len(a):,}")
    c4.metric("Reconciliation", "All pass ✅" if rep["all_pass"] else "FAILS ⚠️")

    with st.container(border=True):
        st.subheader("Reconciliation by file (net vs Eindsaldo)")
        rec = pd.DataFrame(rep["files"])
        st.dataframe(rec.style.format({"net_sum": "{:,.2f}", "eindsaldo": "{:,.2f}"}),
                     use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.subheader("Reconciled revenue — trace to the Excel cell")
        yr = st.selectbox("Year", sorted(a["iso_year"].unique()), key="bk_yr")
        sub = a[a["iso_year"] == yr].head(400)
        st.dataframe(sub[["date", "vat_category", "net_amount", "cash_amount", "doc_no",
                          "source_file", "source_excel_row"]],
                     use_container_width=True, hide_index=True, height=300)
        pick = st.selectbox("Posting", sub["event_id"].tolist(), key="bk_ev")
        s = sub[sub["event_id"] == pick].iloc[0]
        raw = audit.read_excel_row(s["source_file"], int(s["source_excel_row"]))
        st.markdown(f"raw source → `{raw['raw_file']}` (row {raw['key']})")
        st.json({k: str(v) for k, v in (raw["row"] or {}).items()})


# --------------------------------------------------------------------------- #
if role == "Owner":
    owner_view()
elif role == "Operations":
    operations_view()
elif role == "PE Board":
    pe_board_view()
else:
    bookkeeper_view()
