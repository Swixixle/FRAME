"""Public statements index (NewsAPI optional)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from cache.redis import TTL_STATEMENTS, cached_fetch

logger = logging.getLogger(__name__)


async def search_statements(entity_name: str) -> list[dict[str, Any]]:
    key = os.environ.get("NEWSAPI_KEY", "").strip()

    async def factory() -> list[dict[str, Any]]:
        if not key:
            return []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={"q": entity_name, "pageSize": 20, "apiKey": key},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("NewsAPI statements failed: %s", exc)
            return []
        return list(data.get("articles") or [])

    cache_key = f"statements:news:{entity_name.lower().strip()}"
    raw = await cached_fetch(cache_key, TTL_STATEMENTS, factory)
    return raw if isinstance(raw, list) else []
