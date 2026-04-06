"""
Reporter dossiers — CourtListener / disclosures / archives in a later sprint.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from receipt_store import get_stored_reporter_dossier, upsert_reporter_dossier

from services.proportionality_client import (
    fetch_proportionality_packet,
    proportionality_fetch_params_dict,
)


def reporter_slug(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return (s.strip("-") or "unknown")[:120]


def build_reporter_dossier(display_name: str) -> dict[str, Any]:
    slug = reporter_slug(display_name)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "name": display_name.strip() or slug.replace("-", " ").title(),
        "slug": slug,
        "current_outlet": "",
        "outlet_history": [],
        "beat": "",
        "known_for": [],
        "awards": [],
        "lawsuits_involving": [],
        "financial_disclosures": [],
        "notable_corrections": [],
        "coverage_pattern_notes": "",
        "byline_links": [],
        "dossier_generated_at": now,
        "signed": False,
    }


def get_or_build_reporter_dossier(display_name: str, persist: bool = True) -> dict[str, Any]:
    slug = reporter_slug(display_name)
    existing = get_stored_reporter_dossier(slug)
    if existing:
        return existing
    payload = build_reporter_dossier(display_name)
    if persist:
        upsert_reporter_dossier(slug, payload["name"], payload)
    return payload


def _donation_amount_float(donation: dict[str, Any]) -> float | None:
    amt = donation.get("amount")
    if amt is None:
        return None
    try:
        return float(amt)
    except (TypeError, ValueError):
        return None


async def attach_proportionality_packets_to_fec_donations(fec_donations: list[Any] | None) -> None:
    """
    After OpenFEC Schedule A rows are attached to a journalist dossier, add EthicalAlt
    proportionality context per row. Low-confidence name matches are preserved on the row.
    """
    if not fec_donations:
        return
    for donation in fec_donations:
        if not isinstance(donation, dict):
            continue
        amt = _donation_amount_float(donation)
        params = proportionality_fetch_params_dict(
            category="political",
            violation_type="campaign contribution",
            charge_status=None,
            amount_involved=amt,
        )
        donation["proportionality_fetch_params"] = params
        packet = await fetch_proportionality_packet(
            category=params["category"],
            violation_type=params["violation_type"],
            charge_status=params["charge_status"],
            amount_involved=params["amount_involved"],
        )
        donation["proportionality_packet"] = packet


def get_or_build_reporter_by_url_slug(url_slug: str, persist: bool = True) -> dict[str, Any]:
    s = (url_slug or "").strip().lower()
    if not s:
        return build_reporter_dossier("unknown")
    existing = get_stored_reporter_dossier(s)
    if existing:
        return existing
    display = s.replace("-", " ").strip().title()
    payload = build_reporter_dossier(display)
    payload["slug"] = s
    if persist:
        upsert_reporter_dossier(s, payload["name"], payload)
    return payload
