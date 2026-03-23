"""CourtListener API — docket search (optional API key)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from cache.redis import TTL_COURTLISTENER, cached_fetch

logger = logging.getLogger(__name__)


async def search_cases(entity_name: str) -> list[dict[str, Any]]:
    """Best-effort opinion / RECAP search."""

    token = os.environ.get("COURTLISTENER_API_KEY", "").strip()

    async def factory() -> list[dict[str, Any]]:
        if not token:
            return []
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.get(
                    "https://www.courtlistener.com/api/rest/v3/search/",
                    params={"q": entity_name},
                    headers={"Authorization": f"Token {token}"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("CourtListener search failed: %s", exc)
            return []
        return list(data.get("results") or [])

    key = f"courtlistener:search:{entity_name.lower().strip()}"
    raw = await cached_fetch(key, TTL_COURTLISTENER, factory)
    return raw if isinstance(raw, list) else []
