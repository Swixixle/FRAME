"""Route extracted article claims to adapter names (aligned with apps/api/adapters + routes)."""

from __future__ import annotations

from typing import Any

_ORG_SUBSTRINGS = (
    "department",
    "agency",
    "corporation",
    "corp",
    " inc",
    "llc",
    "ltd",
    "administration",
    "committee",
    "bureau",
    "office",
    "ministry",
    "pentagon",
    "congress",
    "senate",
    "house",
    "court",
    "government",
)

_NON_PERSON_TERMS = frozenset(
    {
        "iran",
        "iraq",
        "syria",
        "yemen",
        "israel",
        "russia",
        "china",
        "ukraine",
        "taiwan",
        "japan",
        "korea",
        "germany",
        "france",
        "tehran",
        "jerusalem",
        "moscow",
        "beijing",
        "uk",
        "us",
        "usa",
        "uae",
        "nato",
        "eu",
        "imf",
        "who",
        "un",
        "strait",
        "hormuz",
        "gulf",
        "sea",
        "ocean",
        "houthi",
        "houthis",
        "crude",
        "oil",
        "gas",
        "brent",
        "wti",
        "gold",
        "silver",
        "bitcoin",
        "stock",
        "bond",
        "market",
        "index",
        "futures",
        "commodity",
        "department",
        "agency",
        "bureau",
        "office",
        "administration",
        "committee",
        "congress",
        "senate",
        "house",
        "court",
        "government",
        "ministry",
        "pentagon",
        "fbi",
        "cia",
        "doj",
        "dea",
        "irs",
        "sec",
        "forces",
        "military",
        "army",
        "navy",
        "air",
        "missile",
        "drone",
        "attack",
        "strike",
        "war",
        "conflict",
        "rebel",
        "news",
        "times",
        "post",
        "journal",
        "herald",
        "tribune",
        "media",
        "press",
        "wire",
        "fox",
        "cnn",
        "bbc",
        "reuters",
        "ap",
        "united",
        "states",
        "american",
        "european",
        "arab",
        "league",
    }
)


def is_person_name_for_courtlistener(entity: str) -> bool:
    """
    True only if the string looks like a human person name (2–3 capitalized words).
    Rejects countries, commodities, places, orgs, and concepts — used to gate CourtListener.
    """
    if not entity or not entity.strip():
        return False

    raw = entity.strip().strip('"\'')

    words = [w.strip(".,;:\"'") for w in raw.split() if w.strip()]
    words = [w for w in words if len(w) >= 2]
    if not (2 <= len(words) <= 3):
        return False

    for w in words:
        if not w[0].isupper():
            return False
        wl = w.lower()
        base = wl.rstrip("s") if len(wl) > 1 else wl
        if base in _NON_PERSON_TERMS or wl in _NON_PERSON_TERMS:
            return False
        if w.isupper() and len(w) > 1:
            return False

    sl = raw.lower()
    if any(tok in sl for tok in _ORG_SUBSTRINGS):
        return False

    return True


def subject_looks_like_person(claim: dict[str, Any]) -> bool:
    """Strict person-name gate for CourtListener background checks (not claim-type shortcuts)."""
    subject = str(claim.get("subject") or "").strip()
    if not subject:
        return False
    return is_person_name_for_courtlistener(subject)


def route_claim(claim: dict[str, Any]) -> list[str]:
    """
    Given a claim dict from claim_extractor, return list of adapter names to query.
    Adapters match what already exists in apps/api/adapters/ and the existing endpoint map.
   
    Note: `main.py` also imports `route_claim` from `router` (OCR/media pipeline). Import this
    module's symbols with an alias when both are needed.
    """
    claim_type = str(claim.get("claim_type", "") or "")
    ct = claim_type.lower()
    text = (claim.get("claim") or "").lower()

    adapters: list[str] = []

    if ct in ("rumored", "attribution"):
        adapters.append("courtlistener")

    if claim_type == "financial" or any(
        w in text
        for w in [
            "donation",
            "contribution",
            "campaign finance",
            "pac",
            "super pac",
            "funded",
            "spent",
            "raised",
            "lobbying",
            "lobbyist",
        ]
    ):
        adapters.append("fec")

    if ct in ("legislative", "policy_procedural") or any(
        w in text
        for w in [
            "bill",
            "act",
            "senate",
            "house",
            "congress",
            "legislation",
            "vote",
            "passed",
            "signed",
            "law",
            "amendment",
        ]
    ):
        adapters.append("congress")

    if ct in ("judicial", "legal_regulatory") or any(
        w in text
        for w in [
            "court",
            "ruling",
            "judge",
            "justice",
            "opinion",
            "decision",
            "lawsuit",
            "case",
            "appeal",
            "supreme court",
            "circuit",
        ]
    ):
        adapters.append("courtlistener")

    if ct in ("biographical", "identity_affiliation") or claim.get("subject"):
        adapters.append("actor")
        adapters.append("surface")

    if ct in ("institutional", "factual_state", "factual_event", "statistical", "causal", "chronology"):
        adapters.append("surface")

    if not adapters:
        adapters.append("surface")

    if subject_looks_like_person(claim) and "courtlistener" not in adapters:
        adapters.append("courtlistener")

    return list(dict.fromkeys(adapters))


def build_query_for_adapter(claim: dict[str, Any], adapter: str) -> str:
    """Build an adapter-specific query string from a claim."""
    subject = claim.get("subject", "")
    text = claim.get("claim", "")

    if adapter == "fec":
        return subject or text
    if adapter == "congress":
        return text
    if adapter == "courtlistener":
        if str(claim.get("claim_type") or "").lower() in ("rumored", "attribution"):
            body = str(claim.get("claim") or "")
            return f"{subject} {body[:100]}".strip() or (subject or body)
        return subject or text
    if adapter == "actor":
        subject_str = (subject or text) or ""
        return (
            f"{subject_str} is a named entity referenced in this public record. {subject_str}."
        )
    if adapter == "surface":
        return subject or text

    return text
