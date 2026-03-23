from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Frame(BaseModel):
    id: str
    claim: str
    claimant_name: str
    claimant_role: str
    claimant_organization: str
    timestamp: str
    hash: str
    signature: str
    enrichment_status: Literal["pending", "complete", "failed"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enrichment_error: str | None = None  # populated when status is failed
