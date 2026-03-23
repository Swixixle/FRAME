"""OpenSecrets enrichment (stub + httpx hook when OPENSECRETS_API_KEY set)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from cache.redis import TTL_OPENSECRETS, cached_fetch

logger = logging.getLogger(__name__)


async def get_summary(entity_name: str) -> dict[str, Any]:
    """Campaign finance summary — placeholder until OpenSecrets endpoint wired."""

    key = os.environ.get("OPENSECRETS_API_KEY", "").strip()
    if not key:
        return {"status": "skipped", "reason": "OPENSECRETS_API_KEY not set"}

    cache_key = f"opensecrets:summary:{entity_name.lower().strip()}"

    async def factory() -> dict[str, Any]:
        # Placeholder URL — replace with real OpenSecrets API when available
        logger.info("OpenSecrets stub fetch for %s", entity_name)
        return {"status": "stub", "entity": entity_name}

    raw = await cached_fetch(cache_key, TTL_OPENSECRETS, factory)
    return raw if isinstance(raw, dict) else {"status": "error"}
