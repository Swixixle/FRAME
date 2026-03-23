"""Shared enrichment pipeline for ARQ worker and in-process fallback."""

from __future__ import annotations

import logging
import traceback

from db import fetch_frame, save_frame
from dossier.assemble import assemble_dossier
from entity.resolver import resolve_entity

logger = logging.getLogger(__name__)


async def run_enrich_frame(frame_id: str) -> None:
    frame = await fetch_frame(frame_id)
    if not frame:
        logger.error("run_enrich_frame: missing frame %s", frame_id)
        return
    try:
        resolved = await resolve_entity(
            frame.claimant_name,
            hint=frame.claimant_role or frame.claimant_organization,
        )
        await assemble_dossier(frame_id, resolved)
        frame.enrichment_status = "complete"
        frame.enrichment_error = None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Enrichment failed for %s", frame_id)
        frame.enrichment_status = "failed"
        frame.enrichment_error = f"{exc!r}\n{traceback.format_exc()}"[:800]
    await save_frame(frame)
