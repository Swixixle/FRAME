"""
OpenFEC campaign finance enrichment (schedules A, E, candidate search).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import unicodedata
from typing import Any

import httpx

from cache.redis import TTL_FEC, cached_fetch
from models.dossier import Contribution

logger = logging.getLogger(__name__)

FEC_BASE = "https://api.open.fec.gov/v1/"


def _fec_key() -> str:
    return os.environ.get("FEC_API_KEY", "DEMO_KEY").strip()


def normalize_entity_name(name: str) -> str:
    """Strip titles, lowercase, strip punctuation per spec."""
    s = name.strip()
    for title in (
        "mr ",
        "mrs ",
        "ms ",
        "dr ",
        "sen ",
        "senator ",
        "rep ",
        "representative ",
        "hon ",
    ):
        if s.lower().startswith(title):
            s = s[len(title) :]
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _score_candidate(c: dict[str, Any], name_query: str) -> int:
    score = 0
    office = str(c.get("office") or "").upper()
    # Prefer Senate over House over Presidential
    if office == "S":
        score += 30
    elif office == "H":
        score += 10
    elif office == "P":
        score += 0
    # Prefer closer name match
    cname = str(c.get("name") or "").lower()
    query_lower = name_query.lower()
    # Check if all words in query appear in candidate name
    query_words = query_lower.split()
    if all(w in cname for w in query_words):
        score += 20
    # Prefer more recent activity
    active_through = c.get("active_through") or 0
    try:
        score += min(int(str(active_through)[:4]), 2030) - 2000
    except (ValueError, TypeError):
        pass
    return score


async def _http_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    delays = [1.0, 2.0, 4.0]
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)
                if r.status_code == 429 and attempt < 3:
                    await asyncio.sleep(delays[attempt])
                    continue
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < 3:
                await asyncio.sleep(delays[attempt])
            else:
                logger.warning("FEC HTTP failed after retries: %s", exc)
    return {"results": [], "error": str(last_exc) if last_exc else "unknown"}


async def get_contributions(
    entity_name: str,
    cycles: list[int] | None = None,
) -> list[Contribution]:
    """
    Schedule A: contributor_name filter; top 50 by amount desc.
    """
    cache_key = f"fec:contributions:{normalize_entity_name(entity_name)}"

    async def factory() -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "api_key": _fec_key(),
            "contributor_name": entity_name,
            "per_page": 100,
            "sort": "-contribution_receipt_amount",
        }
        if cycles:
            params["cycle"] = max(cycles)
        data = await _http_get_json(
            f"{FEC_BASE}schedules/schedule_a/",
            params,
        )
        results = data.get("results") or []
        rows: list[dict[str, Any]] = []
        for r in results:
            try:
                amt = float(r.get("contribution_receipt_amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            cm = r.get("committee")
            if isinstance(cm, dict):
                recip = str(cm.get("name") or cm.get("committee_id") or "")
            else:
                recip = str(r.get("committee_name") or r.get("committee_id") or "")
            rows.append(
                {
                    "contributor_name": r.get("contributor_name") or entity_name,
                    "recipient_committee": recip or "unknown",
                    "amount": amt,
                    "transaction_date": r.get("contribution_receipt_date"),
                    "election_cycle": str(r.get("cycle") or "")
                    if r.get("cycle") is not None
                    else None,
                    "fec_url": r.get("transaction_url"),
                }
            )
        rows.sort(key=lambda x: x["amount"], reverse=True)
        return rows[:50]

    raw = await cached_fetch(cache_key, TTL_FEC, factory)
    if raw is None:
        return []
    out: list[Contribution] = []
    for row in raw:
        try:
            out.append(Contribution.model_validate(row))
        except Exception:  # noqa: BLE001
            continue
    return out


async def get_expenditures(entity_name: str) -> list[dict[str, Any]]:
    """Schedule E: independent expenditures; best-effort name filter."""

    async def factory() -> list[dict[str, Any]]:
        params = {
            "api_key": _fec_key(),
            "per_page": 100,
            "payee_name": entity_name,
        }
        data = await _http_get_json(f"{FEC_BASE}schedules/schedule_e/", params)
        return list(data.get("results") or [])

    cache_key = f"fec:expenditures:{normalize_entity_name(entity_name)}"
    raw = await cached_fetch(cache_key, TTL_FEC, factory)
    return raw if isinstance(raw, list) else []


async def get_candidate(entity_name: str) -> dict[str, Any] | None:
    """First candidate search match."""

    async def factory() -> dict[str, Any] | None:
        params = {
            "api_key": _fec_key(),
            "name": entity_name,
            "per_page": 100,
        }
        data = await _http_get_json(f"{FEC_BASE}candidates/search/", params)
        results = data.get("results") or []
        if not results:
            return None
        scored = [(c, _score_candidate(c, entity_name)) for c in results]
        scored.sort(key=lambda x: x[1], reverse=True)
        c = scored[0][0]
        return {
            "candidate_id": c.get("candidate_id"),
            "party": c.get("party"),
            "state": c.get("state"),
            "office": c.get("office"),
            "name": c.get("name"),
        }

    raw = await cached_fetch(
        f"fec:candidate:{normalize_entity_name(entity_name)}",
        TTL_FEC,
        factory,
    )
    if raw is None or not isinstance(raw, dict):
        return None
    return raw


async def get_candidate_totals(entity_name: str) -> dict[str, Any] | None:
    """
    Get career fundraising totals for a candidate.
    First finds candidate_id via get_candidate, then
    queries /candidates/totals/ with candidate_id for financial summary.
    This is the correct way to get "how much has Rand Paul raised"
    rather than schedule_a which shows donations they made to others.
    """
    candidate = await get_candidate(entity_name)
    if not candidate or not candidate.get("candidate_id"):
        return None

    candidate_id = candidate["candidate_id"]

    async def factory() -> dict[str, Any] | None:
        params = {
            "api_key": _fec_key(),
            "candidate_id": candidate_id,
            "per_page": 10,
        }
        data = await _http_get_json(
            f"{FEC_BASE}candidates/totals/",
            params,
        )
        results = data.get("results") or []
        if not results:
            return None
        results.sort(key=lambda r: int(r.get("cycle") or 0), reverse=True)
        most_recent = results[0]

        # Sum across all cycles for career total
        career_receipts = sum(
            float(r.get("receipts") or 0) for r in results
        )
        career_disbursements = sum(
            float(r.get("disbursements") or 0) for r in results
        )

        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.get("name", entity_name),
            "party": candidate.get("party"),
            "state": candidate.get("state"),
            "office": candidate.get("office"),
            "career_total_receipts": career_receipts,
            "career_total_disbursements": career_disbursements,
            "most_recent_cycle": most_recent.get("cycle"),
            "most_recent_receipts": float(
                most_recent.get("receipts") or 0
            ),
            "cycles_found": len(results),
            "fec_url": (
                f"https://www.fec.gov/data/candidate/{candidate_id}/"
            ),
        }

    cache_key = f"fec:totals:{normalize_entity_name(entity_name)}"
    raw = await cached_fetch(cache_key, TTL_FEC, factory)
    if raw is None or not isinstance(raw, dict):
        return None
    return raw
