"""GET /v1/search, /v1/search/suggest — conflict bundles (JSON)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from search_service import run_search, run_suggest

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_json(
    q: str = Query("", description="Search query"),
    volatility_min: int | None = Query(None, ge=0, le=100),
    volatility_max: int | None = Query(None, ge=0, le=100),
    date_range: str = Query("30d", description="24h, 7d, 30d, or 90d"),
    outlet_type: str | None = Query(None, description="state, private, public_broadcaster"),
    region: str | None = Query(None, description="Comma-separated region codes"),
    sort: str = Query("volatility", description="volatility or date"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    return await asyncio.to_thread(
        run_search,
        q,
        volatility_min=volatility_min,
        volatility_max=volatility_max,
        date_range=date_range,
        outlet_type=outlet_type,
        region=region,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/search/suggest")
async def search_suggest(
    q: str = Query("", description="Partial query"),
    limit: int = Query(10, ge=1, le=25),
) -> dict:
    return await asyncio.to_thread(run_suggest, q, limit=limit)
