"""
cash_events.py — Python twin of the UI team's cash_events.js
============================================================

Same role as the JS seed module, but the array is REAL data produced by
ingest.py from the accounting exports, not fake rows. Import it exactly the
way the JS UI imports its module:

    from cash_events import CASH_EVENTS, OPENING_CASH, COVENANT
    from cash_events import (eventsForScenario, weeklyByDriver,
                             runningBalance, traceFigure, opcoExposure)

Regenerate the data with:  python ingest.py --in <uploads> --out <outputs>
(that writes cash_events.json, which this module loads).
"""

import json
import os

# Helper logic lives in ONE place (ingest.py) so the forecast and the
# dashboards can never disagree — re-exported here for a clean import surface.
from ingest import (
    OPENING_CASH,
    COVENANT,
    eventsForScenario,
    weeklyByDriver,
    runningBalance,
    traceFigure,
    opcoExposure,
    window_to_horizon,
    ingest_folder,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "cash_events.json")

# The real, reconciled, 13-week cash_event array. Drop-in for the fake seed.
if os.path.exists(_DATA):
    with open(_DATA, encoding="utf-8") as _f:
        CASH_EVENTS = json.load(_f)
else:                                   # fall back to live ingest if not built yet
    _events, _ = ingest_folder(os.environ.get("ALTIS_UPLOADS", "/mnt/user-data/uploads"))
    CASH_EVENTS = window_to_horizon(_events)

__all__ = [
    "CASH_EVENTS", "OPENING_CASH", "COVENANT",
    "eventsForScenario", "weeklyByDriver", "runningBalance",
    "traceFigure", "opcoExposure",
]
