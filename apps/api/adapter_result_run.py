"""
Structured per-adapter execution for investigation pipelines (stdlib + asyncio only).

Keeps AdapterResult + _run importable without pulling FEC/SEC/adapters.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    adapter: str
    ok: bool
    value: Any = None
    error: Exception | None = None
    timed_out: bool = False
    latency_ms: float = 0.0
    detail: str | None = None
    rows_returned: int | None = None
    source_error: bool = False

    def to_source_record(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "adapter": self.adapter,
            "ok": self.ok,
            "source_error": self.source_error,
            "latency_ms": round(self.latency_ms, 1),
        }
        if self.detail:
            row["detail"] = self.detail[:500]
        if self.rows_returned is not None:
            row["rows_returned"] = self.rows_returned
        if self.timed_out:
            row["timed_out"] = True
        if self.error is not None:
            row["error_type"] = type(self.error).__name__
        return row


async def run_adapter(
    fn: Any,
    *,
    adapter: str,
    timeout: float,
) -> AdapterResult:
    """Run sync (to_thread), coroutine, or coroutine factory. Re-raises asyncio.CancelledError."""
    t0 = time.monotonic()

    def _latency() -> float:
        return (time.monotonic() - t0) * 1000

    try:
        if asyncio.iscoroutine(fn):
            coro = fn
        elif inspect.iscoroutinefunction(fn):
            coro = fn()
        else:
            coro = asyncio.to_thread(fn)
        value = await asyncio.wait_for(coro, timeout=timeout)
        return AdapterResult(adapter=adapter, ok=True, value=value, latency_ms=_latency())
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.warning("[adapter] %s: timeout after %.1fs", adapter, timeout)
        return AdapterResult(
            adapter=adapter,
            ok=False,
            timed_out=True,
            source_error=True,
            detail=f"timeout_after_{timeout}s",
            latency_ms=_latency(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[adapter] %s: %s", adapter, exc)
        return AdapterResult(
            adapter=adapter,
            ok=False,
            error=exc,
            source_error=True,
            detail=str(exc)[:300],
            latency_ms=_latency(),
        )
