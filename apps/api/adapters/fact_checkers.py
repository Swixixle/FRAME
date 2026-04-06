"""
Third-party fact-check aggregation (PolitiFact API; MBFC / FactCheck.org stubs).

Does not claim comprehensive coverage — only what public endpoints allow.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_POLITIFACT_BASE = "https://www.politifact.com/api/v/2/statement/"

_RULING_MAP = {
    "true": "true",
    "mostly-true": "mostly_true",
    "half-true": "half_true",
    "barely-true": "half_true",
    "mostly-false": "mostly_false",
    "false": "false",
    "pants-fire": "pants_on_fire",
    "pants on fire": "pants_on_fire",
}


def _normalize_ruling(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower().replace(" ", "-")
    return _RULING_MAP.get(key) or _RULING_MAP.get(key.replace("-", " "))


def fetch_politifact_aggregate(speaker_name: str, *, limit: int = 20) -> dict[str, Any] | None:
    """
    Pull recent PolitiFact statements for a speaker name (icontains).
    Returns aggregate counts + notable rows, or None on HTTP/error.
    """
    name = (speaker_name or "").strip()
    if len(name) < 2:
        return None
    params = {
        "format": "json",
        "speaker__name__icontains": name[:120],
        "limit": min(max(limit, 1), 50),
        "order_by": "-ruling_date",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(_POLITIFACT_BASE, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("[politifact] %s", exc)
        return None

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return None

    counts: dict[str, int] = {
        "true": 0,
        "mostly_true": 0,
        "half_true": 0,
        "mostly_false": 0,
        "false": 0,
        "pants_on_fire": 0,
    }
    notable: list[dict[str, Any]] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        ruling_obj = row.get("ruling") or {}
        ru = _normalize_ruling(
            ruling_obj.get("ruling") if isinstance(ruling_obj, dict) else str(ruling_obj),
        )
        if ru and ru in counts:
            counts[ru] += 1
        elif ru == "mostly_false":
            counts["mostly_false"] += 1
        if len(notable) < 3 and row.get("statement"):
            notable.append(
                {
                    "statement": (row.get("statement") or "")[:400],
                    "ruling": ru,
                    "url": row.get("canonical_url") or row.get("public_url"),
                    "date": row.get("ruling_date") or row.get("publication_date"),
                },
            )

    total = sum(counts.values())
    falseish = counts["mostly_false"] + counts["false"] + counts["pants_on_fire"]
    false_rate = (falseish / total) if total else 0.0

    return {
        "source": "politifact",
        "speaker_query": name,
        "counts": counts,
        "total": total,
        "false_rate": round(false_rate, 4),
        "notable": notable,
    }


async def get_mbfc_rating(_outlet_name: str, _domain: str) -> dict[str, Any]:
    """
    MBFC has no stable public API. Perplexity / manual research path is deferred.
    """
    _ = (_outlet_name, _domain)
    if not (os.environ.get("PERPLEXITY_API_KEY") or "").strip():
        return {
            "status": "skipped",
            "reason": "PERPLEXITY_API_KEY not set — MBFC snapshot deferred",
        }
    return {"status": "skipped", "reason": "MBFC adapter not implemented"}


async def fetch_factcheck_org_snippets(_person_name: str) -> dict[str, Any]:
    """FactCheck.org: no structured API in this repo yet."""
    _ = _person_name
    return {"status": "skipped", "raw_findings": []}
