"""Tests for _parallel_adapters global budget, task cleanup, and investigation_meta."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parents[1]
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from adapter_result_run import AdapterResult, run_adapter
from first_class_investigation import (
    GLOBAL_INVESTIGATION_TIMEOUT,
    _investigation_meta_from_results,
    _parallel_adapters,
)


def _ar(name: str, **kwargs: object) -> AdapterResult:
    return AdapterResult(adapter=name, **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_global_timeout_cancels_slow_tasks_cleanly():
    """Slow coroutine receives cancellation; no dangling work after _parallel_adapters returns."""
    state = {"slow_started": False, "slow_cancelled": False}

    async def fast() -> AdapterResult:
        return _ar("fast", ok=True, value=1, latency_ms=0.1)

    async def slow() -> AdapterResult:
        state["slow_started"] = True
        try:
            await asyncio.sleep(100.0)
        except asyncio.CancelledError:
            state["slow_cancelled"] = True
            raise
        return _ar("slow", ok=True, value=2, latency_ms=0.1)

    out = await _parallel_adapters([("fast", fast()), ("slow", slow())], budget_s=0.2)
    assert state["slow_started"]
    assert state["slow_cancelled"]
    assert len(out) == 2
    fast_r = next(r for r in out if r.adapter == "fast")
    slow_r = next(r for r in out if r.adapter == "slow")
    assert fast_r.ok is True
    assert slow_r.ok is False and slow_r.timed_out is True


@pytest.mark.asyncio
async def test_global_timeout_does_not_raise_timeout_error_to_caller():
    async def slow() -> AdapterResult:
        await asyncio.sleep(100.0)
        return _ar("slow", ok=True, value=None, latency_ms=1.0)

    try:
        r = await _parallel_adapters([("slow", slow())], budget_s=0.1)
    except asyncio.TimeoutError:
        pytest.fail("caller must not see TimeoutError; results are returned instead")
    assert len(r) == 1
    assert r[0].timed_out is True


@pytest.mark.asyncio
async def test_fast_adapters_complete_when_one_peer_hits_global_budget():
    async def fast_a() -> AdapterResult:
        return _ar("a", ok=True, value="a", latency_ms=1.0)

    async def fast_b() -> AdapterResult:
        return _ar("b", ok=True, value="b", latency_ms=1.0)

    async def slow() -> AdapterResult:
        await asyncio.sleep(100.0)
        return _ar("slow", ok=True, value=None, latency_ms=1.0)

    out = await _parallel_adapters(
        [("a", fast_a()), ("b", fast_b()), ("slow", slow())],
        budget_s=0.25,
    )
    by_adapter = {x.adapter: x for x in out}
    assert by_adapter["a"].ok is True
    assert by_adapter["b"].ok is True
    assert by_adapter["slow"].ok is False
    assert by_adapter["slow"].timed_out is True


@pytest.mark.asyncio
async def test_wall_clock_bounded_under_global_budget():
    async def slow() -> AdapterResult:
        await asyncio.sleep(100.0)
        return _ar("slow", ok=True, value=None, latency_ms=1.0)

    t0 = time.monotonic()
    await _parallel_adapters([("slow", slow())], budget_s=0.15)
    elapsed = time.monotonic() - t0
    assert elapsed < GLOBAL_INVESTIGATION_TIMEOUT + 2.0


@pytest.mark.asyncio
async def test_investigation_meta_shape_from_helpers():
    meta = _investigation_meta_from_results(
        312.4,
        [
            _ar("fec_schedule_a", ok=True, latency_ms=289.1),
            _ar("courtlistener", ok=False, timed_out=True, source_error=True, latency_ms=8001.0),
            _ar("sec_edgar", ok=False, source_error=True, error=RuntimeError("x"), latency_ms=44.2),
        ],
    )
    assert meta["wall_time_ms"] == 312.4
    assert set(meta["adapters"].keys()) == {"fec_schedule_a", "courtlistener", "sec_edgar"}
    assert meta["adapters"]["fec_schedule_a"] == {
        "status": "ok",
        "latency_ms": 289.1,
        "error_type": None,
    }
    assert meta["adapters"]["courtlistener"]["status"] == "timeout"
    assert meta["adapters"]["courtlistener"]["error_type"] is None
    assert meta["adapters"]["sec_edgar"]["status"] == "error"
    assert meta["adapters"]["sec_edgar"]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_parent_task_cancellation_propagates():
    """
    CancelledError from parent (e.g. FastAPI request abort) propagates out of
    _parallel_adapters — it is NOT swallowed or converted to a timeout result.
    """

    async def _slow() -> int:
        await asyncio.sleep(10)
        return 1

    steps = [
        (f"slow_{i}", run_adapter(_slow, adapter=f"slow_{i}", timeout=60.0))
        for i in range(3)
    ]

    task = asyncio.create_task(_parallel_adapters(steps, budget_s=5.0))

    await asyncio.sleep(0.02)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    await asyncio.sleep(0.05)
    pending = [t for t in asyncio.all_tasks() if not t.done()]
    assert not any("slow_" in (t.get_name() or "") for t in pending)
