#!/usr/bin/env python3
"""
ARQ worker — run: cd apps/api && python worker.py
Requires REDIS_URL.
"""

from __future__ import annotations

import asyncio
import logging
import os

from arq.connections import RedisSettings
from arq.worker import run_worker

from worker_tasks import run_enrich_frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def enrich_frame(ctx: dict, frame_id: str) -> None:
    await run_enrich_frame(frame_id)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    )
    functions = [enrich_frame]


if __name__ == "__main__":
    run_worker(WorkerSettings)
