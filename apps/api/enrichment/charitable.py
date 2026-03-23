"""
ProPublica Nonprofit Explorer — IRS 990 charitable enrichment (non-negotiable fields + reasons).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from cache.redis import TTL_IRS990, cached_fetch
from enrichment.fec import normalize_entity_name
from models.dossier import CharitableRecord

logger = logging.getLogger(__name__)

PP_SEARCH = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PP_ORG = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"


async def get_990_filings(ein: str) -> list[dict[str, Any]]:
    """All available 990-related filings metadata for an EIN."""

    async def factory() -> list[dict[str, Any]]:
        url = PP_ORG.format(ein=ein)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_990_filings failed ein=%s: %s", ein, exc)
            return []
        filings = data.get("filings_with_data") or data.get("filings") or []
        if isinstance(filings, list):
            return filings
        return []

    key = f"irs990:{ein}"
    raw = await cached_fetch(key, TTL_IRS990, factory)
    return raw if isinstance(raw, list) else []


async def get_charitable_record(
    entity_name: str,
    ein: str | None = None,
    net_worth_estimate: float | None = None,
) -> CharitableRecord:
    """
    Build CharitableRecord from ProPublica search + org filings.
    Unknown fields → None with reasons entries (never silent omit).
    """

    reasons: dict[str, str] = {}

    async def search_factory() -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(PP_SEARCH, params={"q": ein or entity_name})
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ProPublica search failed: %s", exc)
            return {"organizations": []}

    cache_key = f"irs990:{ein or normalize_entity_name(entity_name)}"
    search = await cached_fetch(cache_key, TTL_IRS990, search_factory)
    if not isinstance(search, dict):
        search = {"organizations": []}

    orgs = search.get("organizations") or []
    primary: dict[str, Any] | None = None
    if orgs:
        primary = orgs[0]
    if ein and orgs:
        for o in orgs:
            if str(o.get("ein", "")).replace("-", "") == ein.replace("-", ""):
                primary = o
                break

    if not primary:
        reasons["total_given_raw"] = "No nonprofit match in ProPublica search for name/EIN."
        reasons["primary_foundation"] = "No organization record selected."
        return CharitableRecord(
            tax_benefit_pct_of_donation=0.37,
            reasons=reasons,
        )

    name = primary.get("name") or entity_name
    ein_val = str(primary.get("ein") or ein or "").replace("-", "")
    filings = await get_990_filings(ein_val) if ein_val else []

    total_giving = 0.0
    for f in filings:
        if not isinstance(f, dict):
            continue
        for k in ("total_giving", "total_gifts", "grants_paid"):
            v = f.get(k)
            if v is not None:
                try:
                    total_giving += float(v)
                except (TypeError, ValueError):
                    continue

    total_given_raw = total_giving if total_giving > 0 else None
    if total_given_raw is None:
        reasons["total_given_raw"] = (
            "Could not sum total_giving from available 990 filing metadata "
            "(fields missing or zero in API response)."
        )

    pct_nw: float | None = None
    if total_given_raw is not None and net_worth_estimate and net_worth_estimate > 0:
        pct_nw = total_given_raw / net_worth_estimate
    else:
        reasons["total_given_pct_net_worth"] = (
            "net_worth_estimate not provided or total_given_raw unavailable."
        )

    tax_benefit: float | None = None
    if total_given_raw is not None:
        tax_benefit = total_given_raw * 0.37
    else:
        reasons["tax_benefit_estimate"] = "total_given_raw unknown."

    board_control: bool | None = None
    investment_discretion: bool | None = None
    family_employed: bool | None = None
    reasons["board_control"] = (
        "Officer/director roster not parsed from this API response in this module version."
    )
    reasons["investment_discretion"] = (
        "Schedule J / investment manager fields not parsed in this module version."
    )
    reasons["family_employed"] = (
        "Surname-based officer crosswalk not performed in this module version."
    )

    shell_entities: list[str] = []
    equity: list[str] = []
    reasons["shell_entities"] = (
        "Related org schedules not cross-walked in this module version."
    )
    reasons["equity_positions_in_funded_sectors"] = (
        "Recipient organizations vs holding-company crosswalk not implemented (best-effort placeholder)."
    )

    return CharitableRecord(
        total_given_raw=total_given_raw,
        total_given_pct_net_worth=pct_nw,
        tax_benefit_estimate=tax_benefit,
        tax_benefit_pct_of_donation=0.37,
        primary_foundation=name,
        board_control=board_control,
        investment_discretion=investment_discretion,
        family_employed=family_employed,
        shell_entities=shell_entities,
        equity_positions_in_funded_sectors=equity,
        reasons=reasons,
    )
