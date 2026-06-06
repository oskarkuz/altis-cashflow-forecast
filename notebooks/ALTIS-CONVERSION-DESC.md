# Altis cash-flow data foundation — Excel → `cash_events`

Converts the raw accounting exports (`*.xlsx` in this folder) into the **one
unified `cash_event` schema** every role/dashboard reads from. The output is a
drop-in replacement for the hand-written `CASH_EVENTS` seed the UI team is
building against — same shape, real reconciled numbers, nothing in the UI
needs to change.

## Run

```bash
pip install openpyxl
python ingest.py --in /path/to/uploads --out /path/to/outputs
```

Options: `--anchor YYYY-MM-DD` sets the forecast start (default = earliest
transaction, so the 13-week window is non-empty out of the box; in production
set it to *today*). `--no-gross-up` keeps net ex-VAT figures instead of cash
incl-VAT.

Writes two files:

| File | What it is |
|---|---|
| `cash_events.json` | The 13-week window, **exact `CASH_EVENTS` shape** — feed this to the UI. |
| `events_normalized.json` | The full lossless timeline with all audit fields — the single source of truth. |

Then from Python: `from cash_events import CASH_EVENTS, runningBalance, traceFigure`.

## Architecture (matches the brief's required layering)

```
ingest  →  normalize  →  reconcile  →  window to 13 weeks  →  serialise
```

Two input layouts reconcile into one schema:

- **FinTransactions** (Exact-style): one GL account per file, named in the
  header; data block under `Nr. | Per. | Datum | Bkst.nr. | Dagboek | Debet |
  Credit`, ending at `Totaal`/`Eindsaldo`.
- **GB / grootboek**: account per row; `Rekening | Periode | Datum |
  Boeknummer | Trek | Debet | Credit | Boekingstekst | Dagboek | BTW |
  BTW-srt`.

`detect_format()` picks the parser automatically. Adding a third/fourth
system = one more parser + a `SOURCE_SYSTEM_BY_FORMAT` entry; nothing
downstream changes.

## The rules (all auditable, all in `CONFIG` at the top of `ingest.py`)

- **Sign:** `net_amount = credit − debit` → positive = inflow, negative =
  outflow. Validated: for every Exact export the summed net equals the file's
  own `Eindsaldo` to the cent (the reconciliation report prints PASS/FAIL).
  The same rule correctly turns future cost-account debits into outflows.
- **GL → driver:** `GL_ACCOUNTS` is the chart-of-accounts mapping. An
  **unknown account doesn't crash** — it routes to an `unmapped` driver with a
  loud assumption tag so a controller sees it (edge case: "new GL account").
- **VAT:** revenue is booked ex-VAT but customers pay incl-VAT, so the cash
  amount is grossed up per account (21% / 9%), while reverse-charge & 0%
  accounts get ×1.00 — correct Dutch treatment. `net_amount` is always kept.
- **Audit trail:** every event carries `source_row_id`, `source_file`,
  `source_excel_row`, `doc_no`, plus the raw `debet`/`credit`. `traceFigure()`
  returns the exact rows behind any number, and they sum back to it.

## Honest note on this dataset

All eight supplied files are **revenue (omzet) accounts** (8000 hoog, 8001 &
8005 verlegd, 8002 laag, 8004 0%), so every converted event is a
`milestone_billing` inflow — there are no materials/subcontractor cost
accounts in these exports, and none are invented. The classifier is wired so
that the day a cost-account export is dropped in, it routes to `materials` /
`subcontractor` automatically (uncomment the placeholder lines in
`GL_ACCOUNTS`).

Cross-system reconciliation flag to review: 2023 account 8002 appears in both
`82604-2023_2…` (Exact, €2,150) and `GB_8002…` (€4,000). They are kept as
distinct sources (tagged `source_system`); a controller should confirm period
coverage before any cross-system dedup.

## Extension points (left as clean hooks, not faked)

- **`payment_lag`** — these rows are the *invoice* event; deriving the cash
  receipt is a shift-forward transform on each `milestone_billing` inflow.
- **`weather`** + **wet/dry scenarios** — produced by stamping `scenario` and
  shifting `week` on a copy of affected events; `eventsForScenario()` already
  merges overrides over base.
