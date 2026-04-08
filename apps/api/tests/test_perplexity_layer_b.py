"""Tests for Perplexity Layer B (mocked HTTP; no real API calls in CI)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_API = Path(__file__).resolve().parents[1]
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

import perplexity_layer_b as plb
from perplexity_layer_b import (
    MODEL_SONAR,
    MODEL_SONAR_PRO,
    PerplexityResult,
    build_journalist_layer_b,
    build_outlet_layer_b,
    query_recant_candidates,
    _query,
)


@pytest.fixture(autouse=True)
def clear_perplexity_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)


@pytest.mark.asyncio
async def test_missing_api_key_returns_failed_results():
    b = await build_journalist_layer_b(
        display_name="Jane Doe",
        publication="Tribune",
        article_topic="health",
        quoted_sources=[],
    )
    assert b["prior_coverage"]["ok"] is False
    assert "PERPLEXITY_API_KEY" in (b["prior_coverage"].get("detail") or "")
    assert b["source_audits"] == []
    assert "wall_time_ms" in b


@pytest.mark.asyncio
async def test_happy_path_mocked_http(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None):
        _ = (url, json, headers)
        payload = {
            "choices": [{"message": {"content": "Summary."}}],
            "citations": ["https://x.com/a"],
        }
        resp = MagicMock(status_code=200, text="{}")
        resp.json = lambda: payload
        return resp

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        r = await _query("hello", field="prior_coverage", model=MODEL_SONAR)

    assert r.ok is True
    assert r.text == "Summary."
    assert r.citations


@pytest.mark.asyncio
async def test_http_error_returns_failed_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None):
        return MagicMock(status_code=503, text="unavailable")

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        r = await _query("hello", field="prior_coverage", model=MODEL_SONAR)

    assert r.ok is False
    assert "http_503" in (r.detail or "")


@pytest.mark.asyncio
async def test_timeout_returns_failed_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    async def boom(self, url, json=None, headers=None):
        raise httpx.TimeoutException("too slow")

    with patch.object(httpx.AsyncClient, "post", new=boom):
        r = await _query("hello", field="prior_coverage", model=MODEL_SONAR)

    assert r.ok is False
    assert "timeout" in (r.detail or "").lower()


@pytest.mark.asyncio
async def test_cancelled_error_propagates_from_query(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")

    async def hang(self, url, json=None, headers=None):
        await asyncio.sleep(100.0)
        return MagicMock(status_code=200, text="{}")

    with patch.object(httpx.AsyncClient, "post", new=hang):
        task = asyncio.create_task(_query("hello", field="prior_coverage", model=MODEL_SONAR))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_all_core_queries_fire(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    mock_q = AsyncMock(
        return_value=PerplexityResult(
            field="x",
            ok=True,
            model=MODEL_SONAR,
            text="t",
            citations=[],
            latency_ms=1.0,
        )
    )
    with patch.object(plb, "_query", mock_q):
        await build_journalist_layer_b(
            display_name="Jane Doe",
            publication="T",
            article_topic=None,
            quoted_sources=[],
        )
    assert mock_q.await_count == 4


@pytest.mark.asyncio
async def test_source_audit_capped_at_three(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    mock_q = AsyncMock(
        return_value=PerplexityResult(
            field="x",
            ok=True,
            model=MODEL_SONAR,
            text="t",
            citations=[],
            latency_ms=1.0,
        )
    )
    quoted = [{"name": f"Person {i}"} for i in range(10)]
    with patch.object(plb, "_query", mock_q):
        b = await build_journalist_layer_b(
            display_name="Jane Doe",
            publication="T",
            article_topic=None,
            quoted_sources=quoted,
            max_source_audits=3,
        )
    assert len(b["source_audits"]) == 3
    assert mock_q.await_count == 4 + 3


@pytest.mark.asyncio
async def test_journalist_not_audited_as_own_source(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    mock_q = AsyncMock(
        return_value=PerplexityResult(
            field="x",
            ok=True,
            model=MODEL_SONAR,
            text="t",
            citations=[],
            latency_ms=1.0,
        )
    )
    quoted = [{"name": "Jane Doe"}, {"name": "Other Person"}]
    with patch.object(plb, "_query", mock_q):
        b = await build_journalist_layer_b(
            display_name="Jane Doe",
            publication="T",
            article_topic=None,
            quoted_sources=quoted,
            max_source_audits=3,
        )
    names = [x["source_name"] for x in b["source_audits"]]
    assert "Jane Doe" not in names
    assert "Other Person" in names
    assert mock_q.await_count == 4 + 1


@pytest.mark.asyncio
async def test_outlet_funding_skipped_when_registry_match(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    mock_q = AsyncMock(
        return_value=PerplexityResult(
            field="x",
            ok=True,
            model=MODEL_SONAR,
            text="t",
            citations=[],
            latency_ms=1.0,
        )
    )
    with patch.object(plb, "_query", mock_q):
        b = await build_outlet_layer_b(
            outlet_name="The Tribune",
            domain="tribune.com",
            registry_match=True,
        )
    assert mock_q.await_count == 1
    assert b["outlet_funding"] is not None
    assert b["outlet_funding"]["ok"] is False
    assert "skipped_registry" in (b["outlet_funding"].get("detail") or "")


@pytest.mark.asyncio
async def test_outlet_funding_runs_for_unknown_outlet(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    mock_q = AsyncMock(
        return_value=PerplexityResult(
            field="x",
            ok=True,
            model=MODEL_SONAR,
            text="t",
            citations=[],
            latency_ms=1.0,
        )
    )
    with patch.object(plb, "_query", mock_q):
        await build_outlet_layer_b(
            outlet_name="Unknown Blog",
            domain="unknown.test",
            registry_match=False,
        )
    assert mock_q.await_count == 2


@pytest.mark.asyncio
async def test_outlet_missing_name_skips(monkeypatch: pytest.MonkeyPatch):
    b = await build_outlet_layer_b(
        outlet_name="unknown",
        domain="",
        registry_match=False,
    )
    assert b["outlet_funding"] is None
    assert b["outlet_ownership"]["ok"] is False


@pytest.mark.asyncio
async def test_layer_b_marker_on_all_records():
    r = PerplexityResult(
        field="prior_coverage",
        ok=True,
        model=MODEL_SONAR,
        text="x",
        citations=["https://a"],
        latency_ms=1.0,
    ).to_record()
    assert r["layer"] == "B"
    assert r["layer_note"] == "web_research_cited_not_signed"

    r2 = PerplexityResult(
        field="outlet_funding",
        ok=False,
        model=MODEL_SONAR,
        detail="skip",
        latency_ms=0.0,
    ).to_record()
    assert r2["layer"] == "B"
    assert r2["layer_note"] == "web_research_cited_not_signed"


@pytest.mark.asyncio
async def test_recant_uses_sonar_pro(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "x")
    seen: list[str] = []

    async def capture_q(prompt: str, *, field: str, model: str = MODEL_SONAR, timeout_s: float = 45.0):
        seen.append(model)
        return PerplexityResult(
            field=field,
            ok=True,
            model=model,
            text="x",
            citations=[],
            latency_ms=1.0,
        )

    with patch.object(plb, "_query", capture_q):
        await query_recant_candidates("A", "Pub", "topic")

    assert seen == [MODEL_SONAR_PRO]


@pytest.mark.asyncio
async def test_journalist_investigation_record_includes_layer_b():
    from adapter_result_run import AdapterResult
    from first_class_investigation import build_journalist_investigation_record

    sentinel = {"prior_coverage": {"layer": "B", "tag": "wired"}, "wall_time_ms": 1.0}

    async def fake_parallel(*_a, **_kw):
        return (
            AdapterResult(adapter="fec_schedule_a", ok=True, value=[], rows_returned=0, latency_ms=1.0),
            AdapterResult(adapter="courtlistener", ok=True, value=[], rows_returned=0, latency_ms=1.0),
            AdapterResult(adapter="propublica_congress_member", ok=True, value=None, latency_ms=1.0),
            AdapterResult(adapter="congress_gov", ok=True, value={}, latency_ms=1.0),
            AdapterResult(adapter="sec_edgar", ok=True, value={}, latency_ms=1.0),
            AdapterResult(adapter="lda", ok=True, value={}, latency_ms=1.0),
        )

    with (
        patch("first_class_investigation._parallel_adapters", side_effect=fake_parallel),
        patch("first_class_investigation._quoted_sources_payload", return_value=[]),
        patch("perplexity_adapter.build_journalist_layer_b", AsyncMock(return_value=sentinel)),
    ):
        result = await build_journalist_investigation_record(
            display_name="Jane Doe",
            publication="The Tribune",
            article_url="https://example.com/article",
            article_topic="healthcare",
            article_text="x",
            named_entities=[],
            linked_article_analysis_id="id-1",
        )

    assert result["layer_b"] == sentinel
