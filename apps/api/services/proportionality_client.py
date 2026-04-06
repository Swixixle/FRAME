"""
Thin client for EthicalAlt /proportionality — does not implement proportionality logic locally.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _proportionality_base() -> str:
    return (os.getenv("PROPORTIONALITY_API_URL") or "https://ethicalalt-api.onrender.com").strip().rstrip("/")


async def fetch_proportionality_packet(
    category: str,
    violation_type: str | None = None,
    charge_status: str | None = None,
    amount_involved: float | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any] | None:
    params: dict[str, str] = {"category": category}
    if violation_type:
        params["violation_type"] = violation_type
    if charge_status:
        params["charge_status"] = charge_status
    if amount_involved is not None:
        params["amount_involved"] = str(amount_involved)
    if lat is not None:
        params["lat"] = str(lat)
    if lng is not None:
        params["lng"] = str(lng)

    base = _proportionality_base()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{base}/proportionality", params=params)
            if res.status_code != 200:
                return None
            data = res.json()
            if not isinstance(data, dict):
                return None
            pkt = data.get("proportionality")
            if isinstance(pkt, dict):
                return pkt
            return data
    except Exception as exc:  # noqa: BLE001
        logger.debug("proportionality fetch failed: %s", exc)
        return None


def proportionality_fetch_params_dict(
    *,
    category: str,
    violation_type: str | None = None,
    charge_status: str | None = None,
    amount_involved: float | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "violation_type": violation_type,
        "charge_status": charge_status,
        "amount_involved": amount_involved,
    }
