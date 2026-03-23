from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EntityType = Literal[
    "corporate_exec",
    "politician",
    "influencer",
    "podcaster",
    "musician",
    "nonprofit",
    "other",
]


class Entity(BaseModel):
    canonical_name: str
    type: EntityType
    organization: str
    fec_candidate_id: str | None = None  # only when linked to OpenFEC candidate
    sec_cik: str | None = None  # only when linked to SEC CIK
    ein: str | None = None  # only when linked to IRS EIN
    social_handles: dict[str, str] | None = None  # optional platform handles when known
    enrichment_path: list[str] = Field(default_factory=list)


class ResolvedEntity(Entity):
    """Persisted resolution result including stable id for DB lookups."""

    id: str
