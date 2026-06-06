"""
AI-ASSISTED GL MAPPING  (+ controller review workflow)
When reconciliation meets an account that isn't in gl_mapping.csv, it doesn't
just dump it in the review bucket — it SUGGESTS a unified account + driver, with
a confidence and a one-line rationale, that a controller can approve or reject.

Two engines, same interface:
  * deterministic  — a semantic/fuzzy matcher over a Dutch construction lexicon
                     (always available, no key, no cost — the demo default).
  * llm            — a real Claude call (used only when ANTHROPIC_API_KEY is set
                     and the `anthropic` SDK is installed); falls back to the
                     deterministic matcher on any error.

Approving a suggestion appends it to gl_mapping_overrides.csv, so the next
pipeline run maps the account automatically (onboarding-by-configuration).
"""
from __future__ import annotations

import difflib
import json
import os

import pandas as pd

from . import config, reconcile

# Keyword -> (unified_account, unified_name, driver). Dutch + English synonyms
# for a construction group's chart of accounts.
LEXICON = [
    (["materiaal", "material", "bouwmateriaal", "grondstof", "duurzaam"],
     ("4000", "Materiaalkosten", "materials")),
    (["onderaann", "onderaanneming", "uitbesteed", "subcontract", "inhuur", "ploeg"],
     ("4100", "Onderaanneming", "subcontractor")),
    (["omzet", "opbrengst", "opbrengsten", "revenue", "termijn", "facturatie", "werk"],
     ("8000", "Projectopbrengsten", "milestone_billing")),
    (["debiteur", "receivable", "te ontvangen", "vordering"],
     ("1300", "Debiteuren", "payment_lag")),
    (["crediteur", "payable", "te betalen", "schuld"],
     ("1600", "Crediteuren", "payment_lag")),
    (["bank", "liquide", "kas", "cash", "rekening"],
     ("1000", "Liquide middelen", "opening_cash")),
    (["algemene", "overhead", "kantoor", "office", "overige", "general"],
     ("4900", "Algemene kosten", "overhead")),
]


def unified_catalog(raw_dir: str | None = None) -> list[dict]:
    """The target chart of accounts (from gl_mapping.csv), de-duplicated."""
    raw_dir = raw_dir or config.RAW
    gm = pd.read_csv(os.path.join(raw_dir, "gl_mapping.csv"), dtype=str).fillna("")
    seen, out = set(), []
    for _, r in gm.iterrows():
        key = r["unified_account"].strip()
        if key in seen:
            continue
        seen.add(key)
        out.append({"unified_account": key, "unified_name": r["unified_name"].strip(),
                    "driver": r["driver"].strip()})
    return out


# --------------------------------------------------------------------------- #
# deterministic semantic matcher
# --------------------------------------------------------------------------- #
def deterministic_suggest(source_account: str, source_name: str,
                          source_system: str = "", catalog=None) -> dict:
    name = (source_name or "").lower()
    best = None
    for keywords, (ua, un, drv) in LEXICON:
        hits = [k for k in keywords if k in name]
        if not hits:
            continue
        # confidence from keyword strength + fuzzy similarity to the unified name
        fuzzy = difflib.SequenceMatcher(None, name, un.lower()).ratio()
        score = min(0.99, 0.6 + 0.15 * len(hits) + 0.25 * fuzzy)
        cand = {"unified_account": ua, "unified_name": un, "driver": drv,
                "confidence": round(score, 2),
                "rationale": f"name contains '{hits[0]}' -> {un} ({ua})",
                "method": "semantic"}
        if best is None or cand["confidence"] > best["confidence"]:
            best = cand
    if best is None:
        best = {"unified_account": "4900", "unified_name": "Algemene kosten",
                "driver": "overhead", "confidence": 0.30,
                "rationale": "no keyword match — defaulting to overhead for review",
                "method": "semantic"}
    return best


# --------------------------------------------------------------------------- #
# optional Claude upgrade (guarded; falls back to deterministic)
# --------------------------------------------------------------------------- #
def llm_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def llm_suggest(source_account: str, source_name: str, source_system: str,
                catalog: list[dict], examples: str = "") -> dict:
    """Ask Claude to map one account to the unified chart of accounts.
    Returns the same dict shape as deterministic_suggest; falls back on error."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        cat = "\n".join(f"- {c['unified_account']} {c['unified_name']} "
                        f"(driver: {c['driver']})" for c in catalog)
        prompt = (
            "You map a source GL account from a Dutch construction company's "
            "accounting system onto a shared chart of accounts.\n\n"
            f"Source system: {source_system}\n"
            f"Source account number: {source_account}\n"
            f"Source account name: {source_name}\n"
            f"Example postings: {examples or 'n/a'}\n\n"
            f"Shared chart of accounts:\n{cat}\n\n"
            "Reply with ONLY a JSON object: "
            '{"unified_account": "<code>", "driver": "<driver>", '
            '"confidence": <0..1>, "rationale": "<short reason>"}')
        msg = client.messages.create(
            model=config.GL_AI.get("model", "claude-haiku-4-5-20251001"),
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        ua = str(data["unified_account"]).strip()
        un = next((c["unified_name"] for c in catalog if c["unified_account"] == ua), ua)
        return {"unified_account": ua, "unified_name": un,
                "driver": str(data.get("driver", "")).strip(),
                "confidence": round(float(data.get("confidence", 0.7)), 2),
                "rationale": str(data.get("rationale", "")).strip(),
                "method": "claude"}
    except Exception as e:  # any failure -> deterministic, never crash the demo
        out = deterministic_suggest(source_account, source_name, source_system, catalog)
        out["rationale"] += f"  [LLM fell back: {type(e).__name__}]"
        return out


def suggest(source_account: str, source_name: str, source_system: str = "",
            examples: str = "", raw_dir: str | None = None) -> dict:
    catalog = unified_catalog(raw_dir)
    if config.GL_AI.get("use_llm", False) and llm_available():
        return llm_suggest(source_account, source_name, source_system, catalog, examples)
    return deterministic_suggest(source_account, source_name, source_system, catalog)


# --------------------------------------------------------------------------- #
# review queue + approve
# --------------------------------------------------------------------------- #
def review_queue(txns: pd.DataFrame, raw_dir: str | None = None) -> pd.DataFrame:
    """Every unmapped account with an AI suggestion + the postings it would affect."""
    raw_dir = raw_dir or config.RAW
    un = txns[txns["driver"] == "UNMAPPED"]
    rows = []
    grp = un.groupby(["source_system", "source_account", "source_account_name"], dropna=False)
    for (sys, acct, name), g in grp:
        examples = "; ".join(g["source_account_name"].astype(str).unique()[:3])
        s = suggest(acct, name, sys, examples, raw_dir)
        rows.append({
            "source_system": sys, "source_account": acct, "source_account_name": name,
            "n_postings": len(g), "amount": g["amount"].sum(),
            "suggested_account": s["unified_account"],
            "suggested_name": s["unified_name"], "suggested_driver": s["driver"],
            "confidence": s["confidence"], "rationale": s["rationale"],
            "engine": s["method"]})
    return pd.DataFrame(rows)


def approve(source_system: str, source_account: str, source_account_name: str,
            unified_account: str, unified_name: str, driver: str,
            raw_dir: str | None = None) -> None:
    """Persist an approved mapping to gl_mapping_overrides.csv (re-run picks it up)."""
    raw_dir = raw_dir or config.RAW
    path = os.path.join(raw_dir, reconcile.OVERRIDES_FILE)
    row = {"source_system": source_system, "source_account": source_account,
           "source_account_name": source_account_name,
           "unified_account": unified_account, "unified_name": unified_name,
           "driver": driver}
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str).fillna("")
        df = df[~((df["source_system"] == source_system) &
                  (df["source_account"] == source_account))]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_csv(path, index=False)
