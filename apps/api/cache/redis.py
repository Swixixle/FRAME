"""
Async Redis client + cached_fetch helper for Frame enrichment modules.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar("T")

TTL_FEC = 86400  # 24 hours
TTL_OPENSECRETS = 86400
TTL_SEC = 86400
TTL_COURTLISTENER = 21600  # 6 hours
TTL_IRS990 = 86400
TTL_SOCIALBLADE = 43200  # 12 hours
TTL_STATEMENTS = 21600

_redis: redis.Redis | None = None


def get_cache() -> redis.Redis | None:
    """
    Returns a shared async Redis client, or None if REDIS_URL is unset/invalid.
    """
    global _redis
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    if _redis is None:
        _redis = redis.from_url(url, decode_responses=True)
    return _redis


async def cached_fetch(
    key: str,
    ttl: int,
    factory: Callable[[], Awaitable[T]],
) -> T | None:
    """
    Return cached JSON value if present; otherwise call factory, store JSON, return.
    On Redis errors: log, return None (caller should treat as cache miss / degraded).
    """
    client = get_cache()
    if client is None:
        try:
            return await factory()
        except Exception as exc:  # noqa: BLE001
            logger.warning("cached_fetch no-redis factory failed: %s", exc)
            return None

    try:
        raw = await client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cached_fetch get failed key=%s: %s", key, exc)
        return None

    try:
        value = await factory()
    except Exception as exc:  # noqa: BLE001
        logger.warning("cached_fetch factory failed key=%s: %s", key, exc)
        return None

    try:
        await client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.warning("cached_fetch set failed key=%s: %s", key, exc)

    return value
