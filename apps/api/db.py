"""
PostgreSQL (asyncpg) with in-memory fallback when DATABASE_URL is unset.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import asyncpg

from models.dossier import DossierSchema
from models.entity import ResolvedEntity
from models.frame import Frame

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# In-memory fallback (dev / no Postgres)
_mem_frames: dict[str, dict[str, Any]] = {}
_mem_entities: dict[str, dict[str, Any]] = {}
_mem_dossiers: dict[str, dict[str, Any]] = {}


async def get_pool() -> asyncpg.Pool | None:
    global _pool
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if _pool is None:
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=8)
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resolved_entities (
                    id UUID PRIMARY KEY,
                    canonical_name TEXT NOT NULL UNIQUE,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS frames (
                    id UUID PRIMARY KEY,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS dossiers (
                    frame_id UUID PRIMARY KEY REFERENCES frames(id),
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT now()
                );
                """
            )
        logger.info("PostgreSQL pool ready.")
    return _pool


async def health_db() -> bool:
    pool = await get_pool()
    if pool is None:
        return True  # in-memory OK for demo
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


async def fetch_resolved_entity(canonical_name: str) -> ResolvedEntity | None:
    key = canonical_name.strip().lower()
    pool = await get_pool()
    if pool is None:
        row = _mem_entities.get(key)
        if not row:
            return None
        return ResolvedEntity.model_validate(row)
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT payload FROM resolved_entities WHERE lower(canonical_name) = lower($1)",
            canonical_name,
        )
        if not r:
            return None
        return ResolvedEntity.model_validate(r["payload"])


async def save_resolved_entity(entity: ResolvedEntity) -> None:
    key = entity.canonical_name.strip().lower()
    payload = entity.model_dump(mode="json")
    pool = await get_pool()
    if pool is None:
        _mem_entities[key] = payload
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO resolved_entities (id, canonical_name, payload)
            VALUES ($1::uuid, $2, $3::jsonb)
            ON CONFLICT (canonical_name) DO UPDATE SET payload = EXCLUDED.payload
            """,
            uuid.UUID(entity.id),
            entity.canonical_name,
            json.dumps(payload),
        )


async def save_frame(frame: Frame) -> None:
    payload = frame.model_dump(mode="json")
    pool = await get_pool()
    if pool is None:
        _mem_frames[frame.id] = payload
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO frames (id, payload) VALUES ($1::uuid, $2::jsonb)
            ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
            """,
            uuid.UUID(frame.id),
            json.dumps(payload),
        )


async def fetch_frame(frame_id: str) -> Frame | None:
    pool = await get_pool()
    if pool is None:
        row = _mem_frames.get(frame_id)
        if not row:
            return None
        return Frame.model_validate(row)
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT payload FROM frames WHERE id = $1::uuid",
            frame_id,
        )
        if not r:
            return None
        return Frame.model_validate(r["payload"])


async def save_dossier(d: DossierSchema) -> None:
    payload = d.model_dump(mode="json")
    pool = await get_pool()
    if pool is None:
        _mem_dossiers[d.frame_id] = payload
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dossiers (frame_id, payload) VALUES ($1::uuid, $2::jsonb)
            ON CONFLICT (frame_id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
            """,
            uuid.UUID(d.frame_id),
            json.dumps(payload),
        )


async def fetch_dossier(frame_id: str) -> DossierSchema | None:
    pool = await get_pool()
    if pool is None:
        row = _mem_dossiers.get(frame_id)
        if not row:
            return None
        return DossierSchema.model_validate(row)
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT payload FROM dossiers WHERE frame_id = $1::uuid",
            frame_id,
        )
        if not r:
            return None
        return DossierSchema.model_validate(r["payload"])
