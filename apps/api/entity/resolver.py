"""
Resolve a public figure name to ResolvedEntity using DB, FEC, SEC, ProPublica, hints.
"""

from __future__ import annotations

import logging
import urllib.parse
import uuid
from typing import Any

import httpx

from db import fetch_resolved_entity, save_resolved_entity
from enrichment import fec
from models.entity import EntityType, ResolvedEntity

logger = logging.getLogger(__name__)

PP_SEARCH = "https://projects.propublica.org/nonprofits/api/v2/search.json"


def _paths_for_type(t: EntityType) -> list[str]:
    table: dict[str, list[str]] = {
        "politician": ["fec:candidate", "fec:contributions", "opensecrets:summary", "courtlistener:search"],
        "corporate_exec": ["sec:edgar", "fec:contributions", "courtlistener:search"],
        "influencer": ["socialblade:channel", "statements:news", "courtlistener:search"],
        "podcaster": ["socialblade:channel", "statements:news"],
        "musician": ["statements:news", "courtlistener:search"],
        "nonprofit": ["propublica:990", "courtlistener:search"],
        "other": ["courtlistener:search", "statements:news"],
    }
    return table.get(t, table["other"])


def _hint_to_type(hint: str | None) -> EntityType | None:
    if not hint:
        return None
    h = hint.lower()
    if "influencer" in h:
        return "influencer"
    if "podcast" in h:
        return "podcaster"
    if "music" in h or "musician" in h:
        return "musician"
    return None


async def _try_pp_nonprofit(name: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(PP_SEARCH, params={"q": name})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ProPublica search failed: %s", exc)
        return None
    orgs = data.get("organizations") or []
    return orgs[0] if orgs else None


async def _try_sec_efts(name: str) -> dict[str, Any] | None:
    try:
        q = urllib.parse.quote(name)
        url = (
            f"https://efts.sec.gov/LATEST/search-index"
            f"?q={q}&dateRange=custom&startdt=2010-01-01"
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                url,
                headers={"User-Agent": "FrameBot/1.0 (research)"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug("EFTS search failed or non-JSON: %s", exc)
        return None
    if isinstance(data, dict):
        return data
    return None


async def resolve_entity(name: str, hint: str | None = None) -> ResolvedEntity:
    stripped = name.strip()
    existing = await fetch_resolved_entity(stripped)
    if existing:
        return existing

    etype: EntityType = "other"
    fec_id: str | None = None
    sec_cik: str | None = None
    ein: str | None = None
    org_guess = ""

    cand = await fec.get_candidate(stripped)
    if cand and cand.get("candidate_id"):
        etype = "politician"
        fec_id = str(cand["candidate_id"])
        org_guess = str(cand.get("office") or "political")

    if etype == "other":
        sec_raw = await _try_sec_efts(stripped)
        hit0: dict[str, Any] | None = None
        if isinstance(sec_raw, dict):
            hits = sec_raw.get("hits")
            try:
                if isinstance(hits, (list, tuple)) and len(hits) > 0:
                    h = hits[0]
                    hit0 = h if isinstance(h, dict) else None
                elif isinstance(hits, dict) and hits:
                    first = next(iter(hits.values()))
                    hit0 = first if isinstance(first, dict) else None
            except (KeyError, TypeError, ValueError, StopIteration) as exc:
                logger.debug("SEC EFTS hits parse skipped: %s", exc)
        if hit0:
            etype = "corporate_exec"
            sec_cik = str(hit0.get("cik") or hit0.get("adsh") or "") or None
            org_guess = str(hit0.get("name") or "")

    if etype == "other":
        pp = await _try_pp_nonprofit(stripped)
        if pp and pp.get("ein"):
            etype = "nonprofit"
            ein = str(pp.get("ein")).replace("-", "")

    if etype == "other":
        inferred = _hint_to_type(hint)
        if inferred:
            etype = inferred
        else:
            etype = "other"

    rid = str(uuid.uuid4())
    resolved = ResolvedEntity(
        id=rid,
        canonical_name=stripped,
        type=etype,
        organization=org_guess or "",
        fec_candidate_id=fec_id,
        sec_cik=sec_cik,
        ein=ein,
        social_handles=None,
        enrichment_path=_paths_for_type(etype),
    )
    await save_resolved_entity(resolved)
    return resolved
