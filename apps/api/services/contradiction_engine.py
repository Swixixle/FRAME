"""
Cross-time contradiction detection from entity_evidence_log (statement clustering).

STUB: run when ≥3 statements exist — implementation deferred until evidence accumulates.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_if_sufficient_sync(entity_slug: str) -> None:
    """Firestore-style hook; safe no-op until statement clustering ships."""
    if not (entity_slug or "").strip():
        return
    logger.debug("[contradiction_engine] stub skip slug=%r", entity_slug)
