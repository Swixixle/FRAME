"""
generated_headline, executive_summary, the_gap — narrative layer over entity_profiles.

STUB: synthesis deferred; does not block investigations.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def synthesize_if_stale_sync(entity_slug: str) -> dict[str, Any] | None:
    if not (entity_slug or "").strip():
        return None
    logger.debug("[narrative_synthesizer] stub skip slug=%r", entity_slug)
    return None
