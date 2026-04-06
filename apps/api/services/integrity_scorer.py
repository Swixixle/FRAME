"""
Integrity record builder from entity_evidence_log (retractions, corrections, fact-checks).

STUB: returns until rubric is implemented.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def refresh_integrity_stub(entity_slug: str) -> None:
    if not (entity_slug or "").strip():
        return
    logger.debug("[integrity_scorer] stub skip slug=%r", entity_slug)
