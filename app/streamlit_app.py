"""
Altis Groep — Weather-Aware 13-Week Cash-Flow Forecast
Single-page app with a role switcher (CFO / Opco MD), a scenario toggle
(base / wet / dry), a covenant headroom indicator, the 13-week forecast by
driver, and a click-to-trace audit drill-down that filters the single
cash_events table down to the raw CSV row behind any figure.
"""
from __future__ import annotations

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import audit, config, pipeline  # noqa: E402

st.set_page_config(page_title="Altis Groep — Cash-Flow Forecast",
                   page_icon="💶", layout="wide")

BAND_COLORS = {"GREEN": "#1a9850", "AMBER": "#f0a000", "RED": "#d73027"}
DRIVER_ORDER = ["milestone_billing", "payment_lag", "materials",
                "subcontractor", "weather"]
DRIVER_COLORS = {
    "milestone_billing": "#2c7fb8", "payment_lag": "#7fcdbb",
    "materials": "#fdae61", "subcontractor": "#f46d43", "weather": "#762a83",
}


def euro(x: float) -> str:
    return f"€{x:,.0f}"


@st.cache_data(show_spinner="Running the five-layer model…")
def load_bundle():
    return pipeline.run()


@st.cache_data
def load_wip():
    df = pd.read_csv(os.path.join(config.RAW, "wip_projects.csv"))
    return df


bundle = load_bundle()

# --------------------------------------------------------------------------- #
# Sidebar: role switcher + scenario toggle + pipeline status
# --------------------------------------------------------------------------- #
st.sidebar.title("Altis Groep")
st.sidebar.caption("Weather-aware 13-week cash-flow forecast")
role = st.sidebar.radio("**Role**", ["CFO", "Opco MD"], index=0)
scenario = st.sidebar.radio(
    "**Scenario**", bundle["scenarios"], index=0,
    format_func=lambda s: {"base": "Base", "wet": "Wet quarter",
                           "dry": "Dry quarter"}[s])

rep = bundle["recon_report"]
st.sidebar.divider()
st.sidebar.markdown("**Pipeline status**")
st.sidebar.write(
    f"- {rep['n_transactions']} transactions from **{rep['n_systems']} systems**\n"
    f"- Unmapped → review: **{rep['n_unmapped']}** "
    f"({', '.join(rep['unmapped_accounts']) or '—'})")
wx = bundle["weather"][scenario]
st.sidebar.write(f"- Weather lost days ({scenario}): **{wx['total_lost']}**")
st.sidebar.caption("Every figure below is a live aggregation of one `cash_events` "
                   "table. Synthetic data, deterministic (seed 42).")


# --------------------------------------------------------------------------- #
# Shared: audit drill-down panel
# --------------------------------------------------------------------------- #
def audit_panel(events: pd.DataFrame, default_week: int, key: str,
                opco: str | None = None):
    st.markdown("#### 🔎 Audit drill-down — trace any figure to its raw CSV row")
    st.caption("Pick a week and driver (the 'figure'); see every cash_event behind "
               "it, then trace one to the original row in the source file.")
    drivers = ["ALL"] + [d for d in DRIVER_ORDER
                         if d in events["driver"].unique()]
    c1, c2, c3 = st.columns(3)
    weeks = ["ALL"] + list(range(1, config.N_WEEKS + 1))
    wk = c1.selectbox("Week", weeks, index=weeks.index(default_week),
                      key=f"{key}_wk")
    drv = c2.selectbox("Driver", drivers, index=0, key=f"{key}_drv")
    incl = c3.checkbox("Include cash beyond wk13", value=False, key=f"{key}_byd")

    fil = audit.drill_down(
        events, scenario=scenario,
        week=None if wk == "ALL" else int(wk),
        driver=None if drv == "ALL" else drv,
        opco=opco, include_beyond=incl)

    total = fil["amount"].sum()
    st.metric(f"Figure = Σ cash_events  (week {wk}, {drv}"
              + (f", {opco}" if opco else "") + ")", euro(total),
              help="This is the exact number the dashboard cell shows — "
                   "it is the sum of the rows in the table below.")

    show = fil.copy()
    show["assumptions"] = show["assumptions"].map(lambda a: "; ".join(a) if a else "")
    show["amount"] = show["amount"].round(0)
    cols = ["event_id", "week", "opco", "driver", "amount", "source_system",
            "source_table", "source_row_id", "project_id", "assumptions",
            "beyond_horizon"]
    st.dataframe(show[cols], use_container_width=True, hide_index=True,
                 height=min(360, 60 + 28 * len(show)))

    if len(fil):
        st.markdown("**Trace one event all the way to the raw source row:**")
        ev_id = st.selectbox("cash_event", fil["event_id"].tolist(), key=f"{key}_ev")
        ev = fil[fil["event_id"] == ev_id].iloc[0].to_dict()
        raw = audit.trace_to_raw(ev, config.RAW)
        tcol1, tcol2 = st.columns([1, 1])
        with tcol1:
            st.markdown("cash_event")
            st.json({k: (str(ev[k]) if k in ("cash_date",) else ev[k])
                     for k in ["event_id", "scenario", "week", "opco", "driver",
                               "amount", "source_system", "source_table",
                               "source_row_id", "assumptions"]})
        with tcol2:
            st.markdown(f"raw source → `data/raw/{raw['raw_file']}`  (key `{raw['key']}`)")
            st.json(raw["row"])


# --------------------------------------------------------------------------- #
# CFO VIEW
# --------------------------------------------------------------------------- #
def cfo_view():
    path = bundle["liquidity"][scenario]
    cov = bundle["covenant"][scenario]
    events = bundle["cash_events"][scenario]

    st.title("CFO — 13-Week Group Cash-Flow & Covenant")
    band = cov["worst_band"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Opening cash", euro(bundle["opening_cash"]))
    k2.metric(f"Min liquidity (wk {cov['min_headroom_week']})",
              euro(cov["min_liquidity"]),
              delta=f"{cov['min_headroom']:+,.0f} € headroom vs floor")
    k3.markdown(
        f"<div style='padding-top:8px'><span style='font-size:0.8rem;color:#666'>"
        f"Covenant (weekly floor {euro(config.COVENANT['liquidity_floor'])})</span><br>"
        f"<span style='background:{BAND_COLORS[band]};color:white;padding:4px 14px;"
        f"border-radius:6px;font-weight:700;font-size:1.1rem'>{band}</span>"
        f"<br><span style='font-size:0.8rem;color:#666'>{cov['breaches']} week(s) "
        f"breaching</span></div>", unsafe_allow_html=True)
    lev = cov["leverage"]
    k4.metric("Leverage at wk13 (≤3.00x)", f"{lev['ratio']:.2f}x",
              delta=f"{lev['headroom_turns']:.2f}x headroom",
              delta_color="normal" if lev["pass"] else "inverse")

    if band == "RED":
        st.error(f"⚠️ **Covenant breach under the {scenario} scenario** — available "
                 f"liquidity falls to {euro(cov['min_liquidity'])} in week "
                 f"{cov['min_headroom_week']}, €{abs(cov['min_headroom']):,.0f} below "
                 f"the €{config.COVENANT['liquidity_floor']:,.0f} floor. Driver: weather "
                 f"delay pushes back-loaded billing past the horizon.")
    elif band == "AMBER":
        st.warning(f"🟠 Headroom thins to {euro(cov['min_headroom'])} in week "
                   f"{cov['min_headroom_week']} — within the warning band but holding.")
    else:
        st.success(f"🟢 Liquidity stays clear of the floor all 13 weeks "
                   f"(min headroom {euro(cov['min_headroom'])}).")

    # --- Covenant headroom indicator -------------------------------------- #
    st.subheader("Covenant headroom — available liquidity vs floor")
    floor = config.COVENANT["liquidity_floor"]
    amber = floor + config.COVENANT["amber_headroom"]
    p = path.copy()
    base_line = alt.Chart(p).mark_line(point=False, color="#333").encode(
        x=alt.X("week:O", title="Week"),
        y=alt.Y("liquidity:Q", title="Available liquidity (€)"))
    pts = alt.Chart(p).mark_point(size=110, filled=True).encode(
        x="week:O", y="liquidity:Q",
        color=alt.Color("band:N",
                        scale=alt.Scale(domain=list(BAND_COLORS),
                                        range=list(BAND_COLORS.values())),
                        legend=alt.Legend(title="Weekly band")),
        tooltip=[alt.Tooltip("week:O"), alt.Tooltip("liquidity:Q", format=",.0f"),
                 alt.Tooltip("headroom:Q", format=",.0f"), "band:N"])
    floor_rule = alt.Chart(pd.DataFrame({"y": [floor]})).mark_rule(
        color=BAND_COLORS["RED"], strokeDash=[6, 4]).encode(y="y:Q")
    amber_rule = alt.Chart(pd.DataFrame({"y": [amber]})).mark_rule(
        color=BAND_COLORS["AMBER"], strokeDash=[2, 4]).encode(y="y:Q")
    st.altair_chart(base_line + pts + floor_rule + amber_rule,
                    use_container_width=True)

    # --- Scenario comparison (shows the weather effect) ------------------- #
    with st.expander("📊 Scenario comparison — what weather does to liquidity", expanded=True):
        comp = []
        for sc in bundle["scenarios"]:
            q = bundle["liquidity"][sc][["week", "liquidity"]].copy()
            q["scenario"] = sc
            comp.append(q)
        comp = pd.concat(comp)
        line = alt.Chart(comp).mark_line(point=True).encode(
            x=alt.X("week:O", title="Week"),
            y=alt.Y("liquidity:Q", title="Available liquidity (€)"),
            color=alt.Color("scenario:N", scale=alt.Scale(
                domain=["base", "wet", "dry"],
                range=["#333", BAND_COLORS["RED"], BAND_COLORS["GREEN"]])),
            tooltip=["scenario:N", "week:O",
                     alt.Tooltip("liquidity:Q", format=",.0f")])
        frule = alt.Chart(pd.DataFrame({"y": [floor]})).mark_rule(
            color=BAND_COLORS["RED"], strokeDash=[6, 4]).encode(y="y:Q")
        st.altair_chart(line + frule, use_container_width=True)
        st.caption("Wet pushes weather-sensitive billing past the horizon → the "
                   "week-11 trough drops through the floor. Base holds; dry clears.")

    # --- 13-week forecast by driver --------------------------------------- #
    st.subheader("13-week forecast by driver")
    weekly = bundle["weekly"][scenario]
    long = weekly.reset_index().melt("week", var_name="driver", value_name="amount")
    bar = alt.Chart(long).mark_bar().encode(
        x=alt.X("week:O", title="Week"),
        y=alt.Y("amount:Q", title="Net cash (€)", stack="zero"),
        color=alt.Color("driver:N",
                        scale=alt.Scale(domain=list(DRIVER_COLORS),
                                        range=list(DRIVER_COLORS.values())),
                        sort=DRIVER_ORDER),
        order=alt.Order("driver:N"),
        tooltip=["week:O", "driver:N", alt.Tooltip("amount:Q", format=",.0f")])
    st.altair_chart(bar, use_container_width=True)

    tbl = weekly.copy()
    tbl["NET"] = tbl.sum(axis=1)
    tbl.loc["TOTAL"] = tbl.sum()
    st.dataframe(tbl.style.format("{:,.0f}"), use_container_width=True)

    st.divider()
    audit_panel(events, default_week=cov["min_headroom_week"], key="cfo")


# --------------------------------------------------------------------------- #
# OPCO MD VIEW
# --------------------------------------------------------------------------- #
def opco_view():
    wip = load_wip()
    txns = bundle["transactions"]
    events = bundle["cash_events"][scenario]
    opcos = sorted(wip["opco"].unique())

    st.title("Opco MD — WIP Exposure & Project Risk")
    opco = st.selectbox("Operating company", opcos, index=0)
    wx = bundle["weather"][scenario]

    pj = wip[wip["opco"] == opco].copy()
    t = txns[txns["opco"] == opco]
    rows = []
    for _, r in pj.iterrows():
        pid = r["project_id"]
        tt = t[t["project_id"] == pid]
        cost_to_date = -tt[tt["driver"].isin(["materials", "subcontractor"])]["amount"].sum()
        billed_to_date = tt[tt["driver"] == "milestone_billing"]["amount"].sum()
        earned = r["contract_value"] * r["pct_complete"]
        ev_p = events[events["project_id"] == pid]
        fwd_bill = ev_p[ev_p["driver"] == "milestone_billing"]["amount"].sum()
        slip = ev_p[(ev_p["driver"] == "milestone_billing") &
                    (ev_p["beyond_horizon"])]["amount"].sum()
        end_wk = int(r["planned_end_week"])
        delay = wx["delay_by_week"].get(end_wk, 0) if r["weather_sensitive"] == "Y" else 0
        if r["weather_sensitive"] == "Y" and slip > 0 and delay >= 2:
            risk = "RED"
        elif r["weather_sensitive"] == "Y" and delay >= 1:
            risk = "AMBER"
        else:
            risk = "GREEN"
        rows.append({
            "project_id": pid, "project": r["project_name"],
            "contract": r["contract_value"], "pct": r["pct_complete"],
            "weather": r["weather_sensitive"], "crew": r["crew_size"],
            "cost_to_date": cost_to_date, "billed_to_date": billed_to_date,
            "earned_uninvoiced": earned - billed_to_date,
            "fwd_billing": fwd_bill, "billing_slips_past_wk13": slip,
            "weather_delay_wk": delay, "risk": risk})
    exp = pd.DataFrame(rows)

    # KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Projects", len(exp))
    k2.metric("WIP earned-but-uninvoiced", euro(exp["earned_uninvoiced"].sum()))
    k3.metric("Forward billing (13wk)", euro(exp["fwd_billing"].sum()))
    k4.metric(f"Billing slipping past wk13 ({scenario})",
              euro(exp["billing_slips_past_wk13"].sum()))

    n_red = (exp["risk"] == "RED").sum()
    if n_red:
        st.error(f"⚠️ {n_red} weather-sensitive project(s) have billing slipping past "
                 f"the 13-week horizon under the {scenario} scenario — this is the "
                 f"cash that drives the group covenant pressure.")

    st.subheader("WIP exposure by project")

    def color_risk(v):
        return f"background-color:{BAND_COLORS[v]};color:white;font-weight:600"
    disp = exp.drop(columns=["project_id"]).copy()
    styled = (disp.style
              .format({"contract": "{:,.0f}", "pct": "{:.0%}",
                       "cost_to_date": "{:,.0f}", "billed_to_date": "{:,.0f}",
                       "earned_uninvoiced": "{:,.0f}", "fwd_billing": "{:,.0f}",
                       "billing_slips_past_wk13": "{:,.0f}"})
              .map(color_risk, subset=["risk"]))
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Project-level risk signal chart: weather delay vs slipping billing
    st.subheader("Project risk signals")
    sig = exp[["project", "weather_delay_wk", "billing_slips_past_wk13", "risk"]].copy()
    chart = alt.Chart(sig).mark_circle().encode(
        x=alt.X("weather_delay_wk:Q", title="Weather delay (weeks)"),
        y=alt.Y("billing_slips_past_wk13:Q", title="Billing slipping past wk13 (€)"),
        size=alt.Size("billing_slips_past_wk13:Q", legend=None),
        color=alt.Color("risk:N", scale=alt.Scale(
            domain=list(BAND_COLORS), range=list(BAND_COLORS.values()))),
        tooltip=["project:N", "weather_delay_wk:Q",
                 alt.Tooltip("billing_slips_past_wk13:Q", format=",.0f"), "risk:N"])
    st.altair_chart(chart, use_container_width=True)

    st.divider()
    audit_panel(events, default_week="ALL", key="md", opco=opco)


# --------------------------------------------------------------------------- #
if role == "CFO":
    cfo_view()
else:
    opco_view()
