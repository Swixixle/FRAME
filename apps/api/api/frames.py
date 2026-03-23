"""POST /frames, GET /frames/{frame_id}."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from db import fetch_frame, save_frame
from frame_crypto import frame_content_hash, sign_frame_digest_hex
from models.frame import Frame

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/frames", tags=["frames"])


class CreateFrameBody(BaseModel):
    claim: str = Field(..., min_length=1)
    claimant_name: str = Field(..., min_length=1)
    claimant_role: str = ""
    claimant_organization: str = ""


async def _enqueue_enrichment(frame_id: str) -> None:
    """ARQ when REDIS_URL set; otherwise run enrichment in-process."""
    from worker_tasks import run_enrich_frame

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(redis_url))
            try:
                # Function name must match worker.py WorkerSettings.functions
                await pool.enqueue_job("enrich_frame", frame_id)
            finally:
                await pool.close()
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("ARQ enqueue failed, in-process fallback: %s", exc)
    await run_enrich_frame(frame_id)


@router.post("")
async def create_frame(body: CreateFrameBody, background: BackgroundTasks) -> Frame:
    ts = datetime.now(timezone.utc).isoformat()
    fid = str(uuid.uuid4())
    digest_hex = frame_content_hash(body.claim, body.claimant_name, ts)
    try:
        sig = sign_frame_digest_hex(digest_hex)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Signing failed: {exc}") from exc

    frame = Frame(
        id=fid,
        claim=body.claim,
        claimant_name=body.claimant_name,
        claimant_role=body.claimant_role,
        claimant_organization=body.claimant_organization,
        timestamp=ts,
        hash=digest_hex,
        signature=sig,
        enrichment_status="pending",
    )
    await save_frame(frame)
    background.add_task(_enqueue_enrichment, fid)
    return frame


@router.get("/{frame_id}")
async def get_frame(frame_id: str) -> Frame:
    f = await fetch_frame(frame_id)
    if not f:
        raise HTTPException(status_code=404, detail="Frame not found")
    return f
