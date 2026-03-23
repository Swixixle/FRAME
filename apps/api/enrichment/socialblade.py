"""Social Blade — stub (requires SOCIALBLADE_API_KEY for real calls)."""

from __future__ import annotations

import logging
import os
from typing import Any

from cache.redis import TTL_SOCIALBLADE, cached_fetch

logger = logging.getLogger(__name__)


async def get_channel_metrics(handle: str) -> dict[str, Any]:
    async def factory() -> dict[str, Any]:
        key = os.environ.get("SOCIALBLADE_API_KEY", "").strip()
        if not key:
            return {"status": "skipped", "reason": "SOCIALBLADE_API_KEY not set"}
        logger.info("SocialBlade stub for %s", handle)
        return {"status": "stub", "handle": handle}

    raw = await cached_fetch(
        f"socialblade:{handle.lower().strip()}",
        TTL_SOCIALBLADE,
        factory,
    )
    return raw if isinstance(raw, dict) else {"status": "error"}
