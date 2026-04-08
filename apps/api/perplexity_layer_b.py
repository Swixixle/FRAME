"""
Layer B — Perplexity Sonar web research (cited, not signed).

Single entrypoint `_query()`; `CancelledError` propagates. All other failures return
a failed ``PerplexityResult`` (no bare exceptions to callers).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"
MODEL_SONAR = "sonar"
MODEL_SONAR_PRO = "sonar-pro"
QUERY_TIMEOUT_S = 45.0


def _api_key() -> str:
    return (os.environ.get("PERPLEXITY_API_KEY") or "").strip()


@dataclass
class PerplexityResult:
    """Outcome of one Sonar call (field id is the Layer B payload key)."""

    field: str
    ok: bool
    model: str
    text: str | None = None
    citations: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    detail: str | None = None

    def to_record(self, **extra: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "layer": "B",
            "layer_note": "web_research_cited_not_signed",
            "ok": self.ok,
            "model": self.model,
            "text": self.text,
            "citations": list(self.citations or []),
            "latency_ms": round(self.latency_ms, 1),
            "detail": self.detail,
        }
        row.update(extra)
        return row


def _fail(field: str, model: str, detail: str, latency_ms: float = 0.0) -> PerplexityResult:
    return PerplexityResult(field=field, ok=False, model=model, detail=detail, latency_ms=latency_ms)


def _parse_citations(data: dict[str, Any]) -> list[str]:
    raw = data.get("citations")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for c in raw:
        if isinstance(c, str) and c.strip():
            out.append(c.strip())
        elif isinstance(c, dict):
            u = c.get("url") or c.get("href")
            if u:
                out.append(str(u).strip())
    return out[:80]


def _parse_content(data: dict[str, Any]) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    ch0 = choices[0]
    if not isinstance(ch0, dict):
        return None
    msg = ch0.get("message")
    if isinstance(msg, dict):
        c = msg.get("content")
        return str(c).strip() if c is not None else None
    return None


async def _query(
    prompt: str,
    *,
    field: str,
    model: str = MODEL_SONAR,
    timeout_s: float = QUERY_TIMEOUT_S,
) -> PerplexityResult:
    """One Perplexity chat completion with ``return_citations: True``."""
    t0 = time.monotonic()
    key = _api_key()
    if not key:
        return _fail(field, model, "PERPLEXITY_API_KEY not set", latency_ms=(time.monotonic() - t0) * 1000)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "return_citations": True,
    }

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        timeout = httpx.Timeout(timeout_s, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(PERPLEXITY_CHAT_URL, json=payload, headers=headers)
    except asyncio.CancelledError:
        raise
    except httpx.TimeoutException as exc:
        ms = (time.monotonic() - t0) * 1000
        logger.warning("[perplexity_layer_b] timeout field=%s: %s", field, exc)
        return _fail(field, model, f"timeout:{exc!s}"[:300], latency_ms=ms)
    except Exception as exc:  # noqa: BLE001
        ms = (time.monotonic() - t0) * 1000
        logger.warning("[perplexity_layer_b] error field=%s: %s", field, exc)
        return _fail(field, model, str(exc)[:300], latency_ms=ms)

    ms = (time.monotonic() - t0) * 1000
    if resp.status_code < 200 or resp.status_code >= 300:
        logger.warning(
            "[perplexity_layer_b] HTTP %s field=%s body=%s",
            resp.status_code,
            field,
            (resp.text or "")[:200],
        )
        return _fail(field, model, f"http_{resp.status_code}", latency_ms=ms)

    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return _fail(field, model, f"invalid_json:{exc!s}"[:300], latency_ms=ms)

    if not isinstance(data, dict):
        return _fail(field, model, "response_not_object", latency_ms=ms)

    text = _parse_content(data)
    cites = _parse_citations(data)
    return PerplexityResult(
        field=field,
        ok=True,
        model=model,
        text=text,
        citations=cites,
        latency_ms=ms,
        detail=None,
    )


async def query_prior_coverage(
    display_name: str,
    publication: str,
    article_topic: str | None,
) -> PerplexityResult:
    pub = (publication or "").strip() or "unknown publication"
    topic = (article_topic or "").strip() or "general beats"
    prompt = (
        f"Summarize prior news coverage and beat history for journalist {display_name!r} "
        f"associated with {pub!r}, especially regarding topic: {topic}. "
        "Use reputable outlets; cite URLs in the response context."
    )
    return await _query(prompt, field="prior_coverage", model=MODEL_SONAR)


async def query_prior_positions(
    display_name: str,
    publication: str,
) -> PerplexityResult:
    pub = (publication or "").strip() or "unknown publication"
    prompt = (
        f"Find op-eds, interviews, podcasts, or public statements where {display_name!r} "
        f"(linked to {pub!r}) stated opinions or positions on public issues. "
        "Cite sources with URLs."
    )
    return await _query(prompt, field="prior_positions", model=MODEL_SONAR)


async def query_affiliations(
    display_name: str,
    publication: str,
) -> PerplexityResult:
    pub = (publication or "").strip() or "unknown publication"
    prompt = (
        f"List fellowships, think tank affiliations, advisory boards, or paid speaking roles "
        f"for {display_name!r} in connection with {pub!r}. Cite sources with URLs."
    )
    return await _query(prompt, field="affiliations", model=MODEL_SONAR)


async def query_recant_candidates(
    display_name: str,
    publication: str,
    article_topic: str | None,
) -> PerplexityResult:
    pub = (publication or "").strip() or "unknown publication"
    topic = (article_topic or "").strip() or "their work"
    prompt = (
        f"Search for corrections, retractions, criticism, or notable reversals of position "
        f"involving {display_name!r} at/near {pub!r}, related to {topic}. "
        "Flag items that look like recant or correction candidates. Cite URLs."
    )
    return await _query(prompt, field="recant_candidates", model=MODEL_SONAR_PRO)


async def query_source_audit(
    source_person_name: str,
    *,
    journalist_name: str,
    publication: str,
) -> PerplexityResult:
    pub = (publication or "").strip() or "unknown publication"
    prompt = (
        f"Background check on {source_person_name!r} as a quoted source in a story by "
        f"{journalist_name!r} ({pub}). Public controversies, FEC-relevant political giving "
        f"mentions, or reliability notes — cite URLs. Do not equate with {journalist_name!r}."
    )
    return await _query(prompt, field="source_audit", model=MODEL_SONAR)


async def query_outlet_ownership(
    outlet_name: str,
    domain: str | None,
) -> PerplexityResult:
    dom = (domain or "").strip() or "unknown domain"
    prompt = (
        f"Who owns or controls the outlet {outlet_name!r} (domain {dom})? "
        "Parent company, nonprofit structure, or major shareholders if public. Cite URLs."
    )
    return await _query(prompt, field="outlet_ownership", model=MODEL_SONAR)


async def query_outlet_funding(
    outlet_name: str,
    domain: str | None,
) -> PerplexityResult:
    dom = (domain or "").strip() or "unknown domain"
    prompt = (
        f"Describe major funding sources, grants, or advertisers publicly associated with "
        f"{outlet_name!r} ({dom}) that are not already obvious from SEC filings. Cite URLs."
    )
    return await _query(prompt, field="outlet_funding", model=MODEL_SONAR)


def _norm_name(s: str) -> str:
    return " ".join((s or "").lower().split())


async def build_journalist_layer_b(
    *,
    display_name: str,
    publication: str,
    article_topic: str | None,
    quoted_sources: list[dict[str, Any]],
    max_source_audits: int = 3,
) -> dict[str, Any]:
    """Run four core Sonar queries concurrently; source audits concurrent, capped."""
    t0 = time.monotonic()
    name = (display_name or "").strip()
    if not name:
        return {
            "prior_coverage": _fail("prior_coverage", MODEL_SONAR, "no_journalist_name").to_record(),
            "prior_positions": _fail("prior_positions", MODEL_SONAR, "no_journalist_name").to_record(),
            "affiliations": _fail("affiliations", MODEL_SONAR, "no_journalist_name").to_record(),
            "recant_candidates": _fail("recant_candidates", MODEL_SONAR_PRO, "no_journalist_name").to_record(),
            "source_audits": [],
            "wall_time_ms": round((time.monotonic() - t0) * 1000, 1),
        }

    core = await asyncio.gather(
        query_prior_coverage(name, publication, article_topic),
        query_prior_positions(name, publication),
        query_affiliations(name, publication),
        query_recant_candidates(name, publication, article_topic),
    )
    prior_r, pos_r, aff_r, rec_r = core

    audit_names: list[str] = []
    for row in quoted_sources or []:
        if not isinstance(row, dict):
            continue
        nm = str(row.get("name") or "").strip()
        if not nm:
            continue
        if _norm_name(nm) == _norm_name(name):
            continue
        audit_names.append(nm)
        if len(audit_names) >= max_source_audits:
            break

    audit_results: list[dict[str, Any]] = []
    if audit_names:
        tasks = [
            query_source_audit(
                nm,
                journalist_name=name,
                publication=publication,
            )
            for nm in audit_names
        ]
        raw_audits = await asyncio.gather(*tasks)
        for nm, ar in zip(audit_names, raw_audits):
            audit_results.append({"source_name": nm, **ar.to_record()})

    wall_ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "prior_coverage": prior_r.to_record(),
        "prior_positions": pos_r.to_record(),
        "affiliations": aff_r.to_record(),
        "recant_candidates": rec_r.to_record(),
        "source_audits": audit_results,
        "wall_time_ms": wall_ms,
    }


async def build_outlet_layer_b(
    *,
    outlet_name: str,
    domain: str | None,
    registry_match: bool,
) -> dict[str, Any]:
    """Ownership always; funding only when registry did not match (unknown outlet)."""
    t0 = time.monotonic()
    oname = (outlet_name or "").strip()
    if not oname or oname.lower() == "unknown":
        skip = _fail("outlet_ownership", MODEL_SONAR, "missing_outlet_name")
        return {
            "outlet_ownership": skip.to_record(),
            "outlet_funding": None,
            "wall_time_ms": round((time.monotonic() - t0) * 1000, 1),
        }

    own_r = await query_outlet_ownership(oname, domain)

    fund_r: PerplexityResult | None
    if registry_match:
        fund_r = PerplexityResult(
            field="outlet_funding",
            ok=False,
            model=MODEL_SONAR,
            detail="skipped_registry_match_public_records",
            latency_ms=0.0,
        )
    else:
        fund_r = await query_outlet_funding(oname, domain)

    wall_ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "outlet_ownership": own_r.to_record(),
        "outlet_funding": fund_r.to_record() if fund_r is not None else None,
        "wall_time_ms": wall_ms,
    }
