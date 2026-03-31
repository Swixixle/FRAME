"""
Fetch additional real articles on the same story so coalition alignment notes
can cite actual coverage (Sprint 1B.0).

Called from analyze-article after claim extraction; non-fatal on failure.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from article_ingest import fetch_article
from comparative_coverage import get_comparative_coverage

logger = logging.getLogger(__name__)

MAX_SOURCES_DEFAULT = 12


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    try:
        p = urlparse(u)
        if not p.netloc:
            return u.lower()
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse(
            (
                (p.scheme or "https").lower(),
                p.netloc.lower(),
                path,
                "",
                p.query,
                "",
            )
        )
    except Exception:  # noqa: BLE001
        return u.lower()


def _fetch_source_row(url: str) -> dict[str, Any] | None:
    try:
        result = fetch_article(url, timeout=20)
        if result.get("fetch_error"):
            return None
        text = (result.get("text") or "").strip()
        if not text or len(text) < 80:
            return None
        snippet = text[:800].strip()
        return {
            "title": result.get("title") or "",
            "outlet": result.get("publication") or "",
            "publication": result.get("publication") or "",
            "url": result.get("url") or url,
            "date": "",
            "snippet": snippet,
            "fetched": True,
            "source": "source_expansion",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch expansion URL %s: %s", url[:80], exc)
        return None


def expand_sources(
    article: dict[str, Any],
    existing_url: str,
    *,
    named_entities: list[str],
    article_topic: str | None = None,
    max_sources: int = MAX_SOURCES_DEFAULT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    GDELT waterfall → NewsAPI → empty; then fetch snippets for unique URLs.
    Returns (expanded rows, full get_comparative_coverage result).
    """
    art = {**article}
    art["named_entities"] = list(named_entities or [])
    if article_topic is not None:
        art["article_topic"] = article_topic

    coverage = get_comparative_coverage(art)

    existing_n = _normalize_url(existing_url)
    seen: set[str] = set()
    if existing_n:
        seen.add(existing_n)

    candidate_urls: list[str] = []
    for a in coverage.get("articles") or []:
        if not isinstance(a, dict):
            continue
        u = a.get("url")
        if not isinstance(u, str) or not u.startswith("http"):
            continue
        n = _normalize_url(u)
        if not n or n in seen:
            continue
        seen.add(n)
        candidate_urls.append(u.strip())
        if len(candidate_urls) >= max_sources * 4:
            break

    if not candidate_urls:
        logger.info(
            "source_expansion: no URL candidates (coverage_found=%s adapter=%s)",
            coverage.get("coverage_found"),
            coverage.get("source_adapter"),
        )
        return [], coverage

    out: list[dict[str, Any]] = []
    for u in candidate_urls:
        if len(out) >= max_sources:
            break
        row = _fetch_source_row(u)
        if row:
            out.append(row)

    logger.info(
        "source_expansion: kept %d sources (candidates=%d) coverage=%s stage=%s",
        len(out),
        len(candidate_urls),
        coverage.get("source_adapter"),
        coverage.get("gdelt_stage"),
    )
    return out, coverage
