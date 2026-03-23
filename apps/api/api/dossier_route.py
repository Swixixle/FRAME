"""GET /frames/{frame_id}/dossier"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from db import fetch_dossier, fetch_frame
from models.dossier import DossierSchema

router = APIRouter(prefix="/frames", tags=["dossier"])


@router.get("/{frame_id}/dossier")
async def get_dossier(frame_id: str) -> DossierSchema | dict[str, Any]:
    frame = await fetch_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    if frame.enrichment_status == "pending":
        return JSONResponse(
            status_code=202,
            content={"status": "pending", "message": "Enrichment in progress"},
        )
    if frame.enrichment_status == "failed":
        raise HTTPException(
            status_code=500,
            detail={"reason": frame.enrichment_error or "Enrichment failed"},
        )
    d = await fetch_dossier(frame_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return d
