"""
Gap 3 — route extracted OCR claims to public-record adapters (v1 heuristics).
"""

from __future__ import annotations

import re
from typing import Any

# Org / nonprofit name signals (v1)
_ORG_HINTS = re.compile(
    r"\b(foundation|fund|institute|association|society|coalition|alliance|charity|nonprofit|"
    r"university|college|hospital|church|ministry|inc\.?|llc|ltd|corp\.?|company)\b",
    re.I,
)

# Very light person-name heuristic: "First Last" style (2–4 tokens, mostly letters)
_NAME_LIKE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$")


def _guess_name_from_text(text: str) -> str:
    """Fallback when Claude omitted entities — e.g. headline with 'Ted Cruz' and a dollar figure."""
    if not text:
        return ""
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text)
    return m.group(1).strip() if m else ""


def _first_entity(claim: dict[str, Any]) -> str:
    entities = claim.get("entities") or []
    if not isinstance(entities, list):
        return ""
    for e in entities:
        s = str(e).strip()
        if s:
            return s
    return ""


def _normalize_claim_type(raw: str) -> str:
    t = (raw or "general").lower().strip()
    # Map OCR variants to router buckets
    if t in ("election",):
        return "financial"
    if t in ("corporate",):
        return "financial"
    return t


def _looks_like_org_nonprofit(name: str) -> bool:
    if not name or len(name) < 3:
        return False
    if _ORG_HINTS.search(name):
        return True
    # All-caps acronyms (e.g. ACLU, AIPAC)
    if re.match(r"^[A-Z]{2,8}$", name.strip()):
        return False
    return False


def _looks_like_politician_name(name: str) -> bool:
    if not name or len(name) < 4:
        return False
    if _looks_like_org_nonprofit(name):
        return False
    if _NAME_LIKE.match(name.strip()):
        return True
    # Senator / Rep titles
    if re.search(r"\b(Sen\.|Senator|Rep\.|Representative|President|VP)\b", name, re.I):
        return True
    parts = name.split()
    return len(parts) >= 2 and parts[0][0:1].isupper() and parts[-1][0:1].isupper()


def route_claim(claim: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Route a single extracted claim to zero or more adapter call specs.

    claim fields (from OCR): text, type, entities, primary_sources

    Returns specs: [{"adapter": "fec"|"irs990"|"lda"|"congress"|"wikidata", "params": {...}}, ...]
    """
    specs: list[dict[str, Any]] = []
    ctype = _normalize_claim_type(str(claim.get("type") or "general"))
    text = str(claim.get("text") or "").strip()
    first = _first_entity(claim)

    if ctype == "financial":
        target = first or _guess_name_from_text(text) or text.split(",")[0][:120].strip()
        if not target:
            return []
        if _looks_like_org_nonprofit(target):
            specs.append({"adapter": "irs990", "params": {"name": target}})
        elif _looks_like_politician_name(target) or first:
            # Prefer FEC when we have a person-like entity or any named entity for money claims
            specs.append({"adapter": "fec", "params": {"name": first or target}})
        return specs

    if ctype == "lobbying":
        name = first or (text[:120] if text else "")
        if name:
            specs.append({"adapter": "lda", "params": {"name": name}})
        return specs

    if ctype == "government_action":
        q = text if len(text) > 10 else (first + " " + text).strip()
        if q:
            specs.append({"adapter": "congress", "params": {"query": q[:500]}})
        return specs

    if ctype == "biographical":
        if first:
            specs.append({"adapter": "wikidata", "params": {"name": first}})
        return specs

    # general | scientific | legal | death_toll | anything else — v1 skip
    return []
