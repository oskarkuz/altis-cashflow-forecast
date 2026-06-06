"""
generate_sample_data.py  —  Altis Groep weather-aware cash-flow forecast
========================================================================
Deterministic (seed=42) generator for a *synthetic* but realistic dataset of a
mid-size Dutch construction group running FOUR operating companies on FOUR
different accounting systems.

Why a generator (not hand-written CSVs)?
  - Reproducible: anyone can regenerate byte-identical inputs -> auditable.
  - Tunable: a controller can change the CONFIG block and re-create the whole
    world (covenant pressure, weather severity, project mix).
  - Honest: makes it explicit the data is synthetic, and *how* it was built.

It writes 10 raw inputs into data/raw/ :
  4 accounting exports  (gilde / yuki / exact / snelstart)  -> deliberately
                         DIFFERENT delimiters, decimal styles, date formats,
                         column names and account numbers.
  gl_mapping.csv         per-system account number -> ONE shared chart of accounts
  opening_balances.csv   per-system trial-balance extract (cash / AR / AP)
  wip_projects.csv       one row per project (incl. weather_sensitive, crew_size)
  milestones.csv         the FORWARD cash plan: billing(+), materials(-), subcontractor(-)
  weather_daily.csv      91 daily rows of precipitation + temperature (forecast window)
  covenant_terms.md      the covenant formula + thresholds (liquidity floor + leverage)

Run:  python scripts/generate_sample_data.py
"""
from __future__ import annotations

import csv
import os
from datetime import date, timedelta

import numpy as np

# --------------------------------------------------------------------------- #
# CONFIG  (a controller can tune the whole synthetic world from here)
# --------------------------------------------------------------------------- #
SEED = 42
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

FORECAST_START = date(2026, 6, 8)          # Monday = start of week 1
N_WEEKS = 13
HISTORY_DAYS = 90                          # length of the actuals window
TODAY = date(2026, 6, 6)                   # "as of" for opening balances

# Four operating companies, each on its own accounting system.
OPCOS = {
    "Altis Bouw BV":        {"system": "exact",     "prefix": "BOUW"},
    "Altis Infra BV":       {"system": "gilde",     "prefix": "INFRA"},
    "Altis Installatie BV": {"system": "yuki",      "prefix": "INST"},
    "Altis Vastgoed BV":    {"system": "snelstart", "prefix": "VAST"},
}

# Opening cash per opco (group total drives the covenant headroom path).
OPENING_CASH = {
    "Altis Bouw BV":        700_000,
    "Altis Infra BV":       380_000,
    "Altis Installatie BV": 320_000,
    "Altis Vastgoed BV":    200_000,
}   # group opening cash = 1_600_000

rng = np.random.default_rng(SEED)


# --------------------------------------------------------------------------- #
# Helpers for the per-system formatting quirks
# --------------------------------------------------------------------------- #
def eur_comma(x: float) -> str:
    """Dutch decimal-comma, thousands-dot:  -1234.5 -> '-1.234,50'."""
    neg = x < 0
    s = f"{abs(x):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("-" if neg else "") + s


def eur_point(x: float) -> str:
    """Plain point-decimal, no thousands sep: -1234.5 -> '-1234.50'."""
    return f"{x:.2f}"


def write_csv(path: str, header: list[str], rows: list[list], delim: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=delim)
        w.writerow(header)
        w.writerows(rows)


def week_to_date(week: int, offset_days: int = 0) -> date:
    """Map a forecast week (1..13) to a concrete date inside that week."""
    return FORECAST_START + timedelta(days=(week - 1) * 7 + offset_days)


# --------------------------------------------------------------------------- #
# 1. PROJECT UNIVERSE  (drives WIP + the forward milestone plan)
# --------------------------------------------------------------------------- #
# weather_sensitive = outdoor work whose schedule slips on lost crew-days.
# Each project: contract value, % complete, cost ratios, billing weeks.
PROJECTS = [
    # id,         opco,                  name,                       contract, pct,  weather, crew, mat_ratio, sub_ratio, bill_weeks
    ("BOUW-01",  "Altis Bouw BV",        "Nieuwbouw Kantoor Lombok",  3_200_000, 0.45, True,  18, 0.34, 0.30, [3, 8, 12]),
    ("BOUW-02",  "Altis Bouw BV",        "Renovatie Stadskantoor",    1_450_000, 0.60, False, 10, 0.30, 0.34, [2, 6, 11]),
    ("BOUW-03",  "Altis Bouw BV",        "Woningen Leidsche Rijn",    2_100_000, 0.25, True,  14, 0.36, 0.28, [4, 9, 13]),
    ("INFRA-01", "Altis Infra BV",       "Herinrichting N201",        2_750_000, 0.40, True,  16, 0.40, 0.26, [3, 7, 12]),
    ("INFRA-02", "Altis Infra BV",       "Rioolvervanging Centrum",   1_180_000, 0.55, True,  12, 0.42, 0.24, [2, 6, 10]),
    ("INFRA-03", "Altis Infra BV",       "Fietsbrug Merwedekanaal",     980_000, 0.30, True,  10, 0.38, 0.30, [5, 9, 13]),
    ("INST-01",  "Altis Installatie BV", "Klimaatinstallatie Hof",      720_000, 0.50, False,  8, 0.45, 0.20, [2, 5, 9]),
    ("INST-02",  "Altis Installatie BV", "Elektra Zorgcomplex",         640_000, 0.35, False,  7, 0.48, 0.18, [3, 7, 11]),
    ("INST-03",  "Altis Installatie BV", "Data/CV Bedrijfshal",         410_000, 0.65, False,  5, 0.50, 0.16, [1, 4, 8]),
    ("VAST-01",  "Altis Vastgoed BV",    "Gebiedsontw. Kade-Oost",    1_900_000, 0.20, True,   9, 0.28, 0.30, [4, 8, 13]),
    ("VAST-02",  "Altis Vastgoed BV",    "Transformatie Pakhuis",       760_000, 0.45, False,  6, 0.32, 0.28, [3, 7, 12]),
    ("VAST-03",  "Altis Vastgoed BV",    "Parkeergarage P+R",         1_240_000, 0.30, True,   8, 0.35, 0.27, [5, 10, 13]),
]

PROJECT_INDEX = {p[0]: p for p in PROJECTS}


# --------------------------------------------------------------------------- #
# 2. ACCOUNTING EXPORTS  (the messy multi-system actuals) + GL MAPPING
# --------------------------------------------------------------------------- #
# Each system uses its own account numbers. The GL mapping translates them into
# ONE shared chart of accounts.  Shared CoA:
#   4000 Materiaalkosten      -> driver materials      (outflow)
#   4100 Onderaanneming       -> driver subcontractor  (outflow)
#   8000 Projectopbrengsten   -> driver milestone_billing (inflow)
#   1300 Debiteuren (AR)      -> driver payment_lag    (inflow)
#   1600 Crediteuren (AP)     -> driver payment_lag    (outflow)
#   1000 Liquide middelen     -> (opening cash, not a forecast driver)
#   4900 Algemene kosten      -> overhead (tracked, not one of the 5 drivers)
#
# Per-system source accounts -> (unified_account, unified_name, driver)
SYSTEM_ACCOUNTS = {
    "exact": {
        "7000": ("4000", "Materiaalkosten",      "materials"),
        "7100": ("4100", "Onderaanneming",       "subcontractor"),
        "8000": ("8000", "Projectopbrengsten",   "milestone_billing"),
        "1300": ("1300", "Debiteuren",           "payment_lag"),
        "1600": ("1600", "Crediteuren",          "payment_lag"),
        "1000": ("1000", "Liquide middelen",     "opening_cash"),
        "4300": ("4900", "Algemene kosten",      "overhead"),
        # 7050 is a NEW sustainability-materials account, intentionally NOT mapped
        # (edge case: must land in the 'unmapped - review' bucket, not crash).
    },
    "gilde": {
        "60000": ("4000", "Materiaalkosten",     "materials"),
        "61000": ("4100", "Onderaanneming",      "subcontractor"),
        "80000": ("8000", "Projectopbrengsten",  "milestone_billing"),
        "13000": ("1300", "Debiteuren",          "payment_lag"),
        "16000": ("1600", "Crediteuren",         "payment_lag"),
        "10000": ("1000", "Liquide middelen",    "opening_cash"),
        "65000": ("4900", "Algemene kosten",     "overhead"),
    },
    "yuki": {
        "4000": ("4000", "Materiaalkosten",      "materials"),
        "4400": ("4100", "Onderaanneming",       "subcontractor"),
        "8100": ("8000", "Projectopbrengsten",   "milestone_billing"),
        "1200": ("1300", "Debiteuren",           "payment_lag"),
        "1700": ("1600", "Crediteuren",          "payment_lag"),
        "1100": ("1000", "Liquide middelen",     "opening_cash"),
        "4800": ("4900", "Algemene kosten",      "overhead"),
    },
    "snelstart": {
        "4500": ("4000", "Materiaalkosten",      "materials"),
        "4600": ("4100", "Onderaanneming",       "subcontractor"),
        "8200": ("8000", "Projectopbrengsten",   "milestone_billing"),
        "1305": ("1300", "Debiteuren",           "payment_lag"),
        "1605": ("1600", "Crediteuren",          "payment_lag"),
        "1110": ("1000", "Liquide middelen",     "opening_cash"),
        "4950": ("4900", "Algemene kosten",      "overhead"),
    },
}

RELATIONS = ["Bouwmaat NL", "Saint-Gobain", "Van Dijk Onderaanneming", "BAM Infra",
             "Heijmans", "Strukton", "Gemeente Utrecht", "Provincie Utrecht",
             "Wonen Centraal", "Klaassen Staal", "Cementbouw", "Installtech BV"]


def gen_accounting_exports() -> dict[str, int]:
    """Generate ~90 days of actuals per system. Returns row counts."""
    counts = {}
    # group projects by opco
    by_opco: dict[str, list] = {}
    for p in PROJECTS:
        by_opco.setdefault(p[1], []).append(p)

    for opco, meta in OPCOS.items():
        sys = meta["system"]
        accts = list(SYSTEM_ACCOUNTS[sys].keys())
        cost_accts = [a for a in accts if SYSTEM_ACCOUNTS[sys][a][2] in
                      ("materials", "subcontractor", "overhead")]
        rev_acct = [a for a in accts if SYSTEM_ACCOUNTS[sys][a][2] == "milestone_billing"][0]
        ar_acct = [a for a in accts if SYSTEM_ACCOUNTS[sys][a][2] == "payment_lag"
                   and SYSTEM_ACCOUNTS[sys][a][1] == "Debiteuren"][0]
        ap_acct = [a for a in accts if SYSTEM_ACCOUNTS[sys][a][2] == "payment_lag"
                   and SYSTEM_ACCOUNTS[sys][a][1] == "Crediteuren"][0]
        projs = by_opco[opco]

        rows = []
        n_post = rng.integers(70, 95)
        for i in range(int(n_post)):
            d = TODAY - timedelta(days=int(rng.integers(1, HISTORY_DAYS)))
            proj = projs[int(rng.integers(0, len(projs)))]
            roll = rng.random()
            if roll < 0.42:           # cost posting (materials / sub / overhead)
                acct = cost_accts[int(rng.integers(0, len(cost_accts)))]
                amt = -float(rng.integers(3_000, 45_000))
                rel = RELATIONS[int(rng.integers(0, len(RELATIONS)))]
            elif roll < 0.70:         # revenue (billed) -> also creates AR
                acct = rev_acct
                amt = float(rng.integers(20_000, 160_000))
                rel = "Opdrachtgever " + proj[0]
            elif roll < 0.85:         # AR collection
                acct = ar_acct
                amt = float(rng.integers(15_000, 120_000))
                rel = "Opdrachtgever " + proj[0]
            else:                     # AP payment
                acct = ap_acct
                amt = -float(rng.integers(8_000, 60_000))
                rel = RELATIONS[int(rng.integers(0, len(RELATIONS)))]
            rows.append((d, acct, SYSTEM_ACCOUNTS[sys][acct][1], proj[0], rel, amt))

        # --- EDGE CASE 1: a NEW, unmapped GL account (Exact only) ---
        if sys == "exact":
            for _ in range(2):
                d = TODAY - timedelta(days=int(rng.integers(1, 20)))
                rows.append((d, "7050", "Materiaal - duurzaam (nieuw)",
                             projs[0][0], "EcoBouw Supplies", -float(rng.integers(5_000, 18_000))))

        # --- EDGE CASE 2: a late correction journal (re-runs cleanly) ---
        dC = TODAY - timedelta(days=2)
        rows.append((dC, cost_accts[0], SYSTEM_ACCOUNTS[sys][cost_accts[0]][1],
                     projs[0][0], "CORRECTIE boeking", float(rng.integers(2_000, 9_000))))

        rows.sort(key=lambda r: r[0])

        # --- write with the per-system quirks ---
        path = os.path.join(RAW, f"{sys}_export.csv")
        if sys == "exact":
            # comma-delimited, point decimal, US date MM/DD/YYYY
            hdr = ["JournalEntryID", "EntryDate", "GLAccountCode",
                   "GLAccountDescription", "CostCenter", "Relation", "AmountDC"]
            out = []
            for j, (d, acct, name, proj, rel, amt) in enumerate(rows, 1):
                out.append([f"EXJ{j:05d}", d.strftime("%m/%d/%Y"), acct, name,
                            proj, rel, eur_point(amt)])
            write_csv(path, hdr, out, ",")
        elif sys == "gilde":
            # semicolon-delimited, decimal comma, EU date DD-MM-YYYY, Debet/Credit split
            hdr = ["Boekstuknr", "Boekdatum", "Grootboek", "Omschrijving",
                   "Project", "Relatie", "Debet", "Credit"]
            out = []
            for j, (d, acct, name, proj, rel, amt) in enumerate(rows, 1):
                debet = eur_comma(amt) if amt < 0 else ""      # cost = debet
                credit = eur_comma(amt) if amt > 0 else ""     # income = credit
                # store as positive magnitudes in the relevant column
                debet = eur_comma(abs(amt)) if amt < 0 else ""
                credit = eur_comma(abs(amt)) if amt > 0 else ""
                out.append([f"GLD-{j:05d}", d.strftime("%d-%m-%Y"), acct, name,
                            proj, rel, debet, credit])
            write_csv(path, hdr, out, ";")
        elif sys == "yuki":
            # comma-delimited, point decimal, ISO date YYYY-MM-DD
            hdr = ["EntryID", "Date", "GLAccount", "GLDescription",
                   "ProjectCode", "Contact", "AmountEUR"]
            out = []
            for j, (d, acct, name, proj, rel, amt) in enumerate(rows, 1):
                out.append([f"YK{j:06d}", d.strftime("%Y-%m-%d"), acct, name,
                            proj, rel, eur_point(amt)])
            write_csv(path, hdr, out, ",")
        else:  # snelstart
            # semicolon-delimited, decimal comma, EU date DD/MM/YYYY
            hdr = ["Regelnr", "Datum", "Grootboeknr", "Omschrijving",
                   "Projectcode", "Debiteur", "BedragEUR"]
            out = []
            for j, (d, acct, name, proj, rel, amt) in enumerate(rows, 1):
                out.append([f"SS{j:05d}", d.strftime("%d/%m/%Y"), acct, name,
                            proj, rel, eur_comma(amt)])
            write_csv(path, hdr, out, ";")
        counts[sys] = len(rows)
    return counts


def gen_gl_mapping() -> None:
    hdr = ["source_system", "source_account", "source_account_name",
           "unified_account", "unified_name", "driver"]
    rows = []
    for sys, accts in SYSTEM_ACCOUNTS.items():
        for src, (ua, un, drv) in accts.items():
            rows.append([sys, src, accts[src][1], ua, un, drv])
    write_csv(os.path.join(RAW, "gl_mapping.csv"), hdr, rows, ",")


# --------------------------------------------------------------------------- #
# 3. OPENING BALANCES  (trial-balance extract per system -> payment_lag driver)
# --------------------------------------------------------------------------- #
def gen_opening_balances() -> None:
    hdr = ["balance_id", "opco", "source_system", "as_of_date",
           "account_type", "amount"]
    rows = []
    bid = 1
    for opco, meta in OPCOS.items():
        sys = meta["system"]
        # cash
        rows.append([f"OB{bid:04d}", opco, sys, TODAY.isoformat(),
                     "cash", eur_point(OPENING_CASH[opco])]); bid += 1
        # open AR (to be collected) and open AP (to be paid)
        ar = float(rng.integers(280_000, 620_000))
        ap = float(rng.integers(220_000, 480_000))
        rows.append([f"OB{bid:04d}", opco, sys, TODAY.isoformat(),
                     "AR", eur_point(ar)]); bid += 1
        rows.append([f"OB{bid:04d}", opco, sys, TODAY.isoformat(),
                     "AP", eur_point(-ap)]); bid += 1
    write_csv(os.path.join(RAW, "opening_balances.csv"), hdr, rows, ",")


# --------------------------------------------------------------------------- #
# 4. WIP PROJECTS + FORWARD MILESTONE PLAN
# --------------------------------------------------------------------------- #
def gen_wip_projects() -> None:
    hdr = ["project_id", "project_name", "opco", "contract_value",
           "pct_complete", "weather_sensitive", "crew_size",
           "planned_end_week", "location"]
    rows = []
    for pid, opco, name, contract, pct, weather, crew, mat_r, sub_r, bweeks in PROJECTS:
        rows.append([pid, name, opco, eur_point(contract), f"{pct:.2f}",
                     "Y" if weather else "N", crew, max(bweeks), "Utrecht"])
    write_csv(os.path.join(RAW, "wip_projects.csv"), hdr, rows, ",")


def gen_milestones() -> None:
    """The FORWARD cash plan: billing(+), materials(-), subcontractor(-),
    project-linked so the weather cascade can shift the right project's rows.

    Shaped as a realistic construction working-capital profile (deterministic):
      - MATERIALS  front-loaded   (you buy & build before you can bill)
      - SUBCONTRACTOR mid-loaded  (peaks in the middle of the work)
      - BILLING    back-loaded    (termijnen grow; final termijn is largest)
    With short cost-payment lags and longer client terms (config.py), this puts
    cost-heavy weeks in the middle of the 13-week window while most billing
    collects near/after the horizon -> a genuine mid/late-quarter cash trough.
    """
    hdr = ["milestone_id", "project_id", "planned_week", "planned_date",
           "driver", "amount", "description"]
    rows = []
    mid = 1
    for pid, opco, name, contract, pct, weather, crew, mat_r, sub_r, bweeks in PROJECTS:
        remaining = contract * (1 - pct)
        maxw = max(bweeks)
        active_weeks = list(range(1, maxw + 1))

        # ---- billing milestones (inflow): back-loaded weights, final termijn biggest
        bw = np.array([1.0, 1.7, 2.6, 3.2][:len(bweeks)])
        bw = bw / bw.sum()
        for k, wk in enumerate(bweeks):
            amt = round(remaining * float(bw[k]) / 1000) * 1000
            rows.append([f"M{mid:04d}", pid, wk, week_to_date(wk, 2).isoformat(),
                         "milestone_billing", eur_point(amt),
                         f"Termijn {k+1} {name}"]); mid += 1

        # ---- materials commitments (outflow): front-loaded (decreasing weight)
        mat_budget = remaining * mat_r
        mw = np.linspace(1.5, 0.4, len(active_weeks))
        mw = mw / mw.sum()
        for wk, frac in zip(active_weeks, mw):
            amt = round(mat_budget * float(frac) / 500) * 500
            if amt < 1500:
                continue
            rows.append([f"M{mid:04d}", pid, wk, week_to_date(wk, 1).isoformat(),
                         "materials", eur_point(-amt),
                         f"Materiaal PO {name} wk{wk}"]); mid += 1

        # ---- subcontractor commitments (outflow): mid-loaded (triangular peak)
        sub_budget = remaining * sub_r
        midw = (1 + maxw) / 2.0
        sw = np.array([1.0 / (1.0 + abs(wk - midw)) for wk in active_weeks])
        sw = sw / sw.sum()
        for wk, frac in zip(active_weeks, sw):
            amt = round(sub_budget * float(frac) / 500) * 500
            if amt < 1500:
                continue
            rows.append([f"M{mid:04d}", pid, wk, week_to_date(wk, 3).isoformat(),
                         "subcontractor", eur_point(-amt),
                         f"Onderaanneming {name} wk{wk}"]); mid += 1
    write_csv(os.path.join(RAW, "milestones.csv"), hdr, rows, ",")


# --------------------------------------------------------------------------- #
# 5. WEATHER  (daily precip + temp over the 13-week forecast window)
# --------------------------------------------------------------------------- #
def gen_weather() -> None:
    """91 daily rows. NL late-summer pattern: mostly dry with two modest wet
    spells (weeks 3-4 and 8-9). Tuned so BASE is benign (~6-8 lost days >5mm);
    the wet/dry SCENARIOS scale precipitation to create the schedule contrast."""
    hdr = ["date", "precipitation_mm", "temp_min_c", "temp_max_c", "location"]
    rows = []
    n_days = N_WEEKS * 7
    for i in range(n_days):
        d = FORECAST_START + timedelta(days=i)
        wk = i // 7 + 1
        # base seasonal temps (June->Sept, Utrecht) — no frost in this window
        tmax = 22 + 4 * np.sin(i / 30) + rng.normal(0, 2.5)
        tmin = tmax - rng.uniform(7, 11)
        # base precip: dry most days, light drizzle occasionally
        base_p = max(0.0, rng.gamma(0.40, 1.6) - 0.8)
        # wet spells (weeks 4 and 9): precipitation sits in a BORDERLINE band
        # (~3-7mm) so the base scenario loses ~1/3 of days, the wet scenario
        # (x1.6) loses nearly all of them, and the dry scenario (x0.4) loses none.
        if wk in (4, 9):
            base_p = max(base_p, float(rng.uniform(3.2, 7.0)))
        # a couple of lighter unsettled days mid-spell for texture
        elif wk in (3, 8) and rng.random() < 0.35:
            base_p += float(rng.uniform(2.0, 4.5))
        precip = round(float(base_p), 1)
        rows.append([d.isoformat(), f"{precip:.1f}",
                     f"{tmin:.1f}", f"{tmax:.1f}", "Utrecht"])
    write_csv(os.path.join(RAW, "weather_daily.csv"), hdr, rows, ",")


# --------------------------------------------------------------------------- #
# 6. COVENANT TERMS
# --------------------------------------------------------------------------- #
COVENANT_MD = """# Altis Groep — Financing Covenant Terms (extract)

_Facility agreement between Altis Groep B.V. and ING Bank N.V., as agent._

## 1. Liquidity covenant (tested WEEKLY — primary 13-week control)
The Group shall maintain **Available Liquidity of not less than EUR 500,000**
("the Liquidity Floor") at the end of each calendar week.

- **Available Liquidity** = Group cash and cash equivalents
  + undrawn committed Revolving Credit Facility (RCF).
- **Committed RCF** = EUR 0 undrawn for the purposes of the 13-week test
  (facility is currently fully utilised; the weekly test is on cash only).
- **Headroom** = Available Liquidity − Liquidity Floor.

### Warning bands (for the dashboard indicator)
| Band  | Condition                                   |
|-------|---------------------------------------------|
| GREEN | Headroom ≥ EUR 250,000                      |
| AMBER | 0 ≤ Headroom < EUR 250,000  (within EUR 250k of the floor) |
| RED   | Headroom < 0  (Liquidity Floor BREACHED)    |

## 2. Leverage covenant (tested QUARTERLY — informational at week 13)
**Net Debt / LTM EBITDA ≤ 3.00x**, tested on the last day of each quarter.

- **Net Debt** = total interest-bearing debt − cash. Total debt = EUR 9,800,000.
- **LTM EBITDA** = EUR 3,600,000.
- Covenant headroom at quarter end is reported alongside the liquidity test.

## Notes
- The weekly liquidity test is the binding constraint inside a 13-week horizon.
- Parameters above (floor, warning bands, debt, EBITDA) are read by the model
  from this document's values and are adjustable in config.py.
"""


def gen_covenant() -> None:
    with open(os.path.join(RAW, "covenant_terms.md"), "w", encoding="utf-8") as fh:
        fh.write(COVENANT_MD)


# --------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(RAW, exist_ok=True)
    counts = gen_accounting_exports()
    gen_gl_mapping()
    gen_opening_balances()
    gen_wip_projects()
    gen_milestones()
    gen_weather()
    gen_covenant()
    print("Generated synthetic Altis Groep dataset in", os.path.abspath(RAW))
    for sys, n in counts.items():
        print(f"  {sys+'_export.csv':<22} {n:>4} rows")
    print("  gl_mapping.csv, opening_balances.csv, wip_projects.csv,")
    print("  milestones.csv, weather_daily.csv, covenant_terms.md")


if __name__ == "__main__":
    main()
