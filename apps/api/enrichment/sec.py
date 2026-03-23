"""SEC EDGAR — company / insider search (lightweight httpx)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from cache.redis import TTL_SEC, cached_fetch

logger = logging.getLogger(__name__)


async def search_company(name: str) -> dict[str, Any] | None:
    """
    Subprocess-style search against SEC data sets (best effort).
    Uses submissions index JSON when available.
    """

    async def factory() -> dict[str, Any] | None:
        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {"action": "getcompany", "company": name, "output": "json"}
        headers = {"User-Agent": "FrameBot/1.0 (research; contact: frame.local)"}
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SEC browse-edgar failed: %s", exc)
            return None
        return data if isinstance(data, dict) else None

    key = f"sec:company:{name.lower().strip()}"
    raw = await cached_fetch(key, TTL_SEC, factory)
    return raw if isinstance(raw, dict) else None


async def get_filings_for_cik(cik: str) -> list[dict[str, Any]]:
    """Recent filings for CIK (simplified)."""

    async def factory() -> list[dict[str, Any]]:
        headers = {"User-Agent": "FrameBot/1.0 (research; contact: frame.local)"}
        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SEC submissions failed cik=%s: %s", cik, exc)
            return []
        filings = data.get("filings", {})
        recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
        forms = recent.get("form", [])
        out = [{"form": forms[i]} for i in range(min(10, len(forms)))]
        return out

    key = f"sec:filings:{cik}"
    raw = await cached_fetch(key, TTL_SEC, factory)
    return raw if isinstance(raw, list) else []
