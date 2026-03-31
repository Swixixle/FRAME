"""Tests for GDELT waterfall + NewsAPI fallback + empty coverage handling."""

from __future__ import annotations

from unittest.mock import patch

from comparative_coverage import format_coverage_for_prompt, get_comparative_coverage


def _sample_article() -> dict:
    return {
        "url": "https://example.com/news/1",
        "title": "Senate Bill Would Cap Drug Prices in Nine States",
        "text": "The proposal faces opposition. " * 40 + "Acme Corp and Senator Jane Smith spoke.",
        "publication": "Example News",
        "author": "Pat Reporter",
        "named_entities": ["Pat Reporter", "Jane Smith", "Acme Corp", "United States Senate"],
        "article_topic": "Legislation on prescription drug pricing.",
    }


def test_newsapi_fallback_after_gdelt_empty():
    fakeNews = [
        {
            "url": "https://other.test/article",
            "title": "Related",
            "outlet": "Other",
            "ecosystem": "unknown",
            "published": "",
            "source": "newsapi",
            "_source_adapter": "newsapi",
        }
    ]
    with (
        patch(
            "comparative_coverage.fetch_gdelt_coverage",
            return_value=([], None),
        ),
        patch(
            "comparative_coverage.fetch_newsapi_coverage",
            return_value=fakeNews,
        ),
    ):
        r = get_comparative_coverage(_sample_article())
    assert r["coverage_found"] is True
    assert r["source_adapter"] == "newsapi"
    assert r["failure_reason"] is None
    assert len(r["articles"]) == 1


def test_total_failure_no_raise():
    with (
        patch(
            "comparative_coverage.fetch_gdelt_coverage",
            return_value=([], None),
        ),
        patch("comparative_coverage.fetch_newsapi_coverage", return_value=[]),
    ):
        r = get_comparative_coverage(_sample_article())
    assert r["coverage_found"] is False
    assert r["failure_reason"]
    assert r["source_adapter"] == "none"
    assert r["articles"] == []


def test_format_coverage_for_prompt_returns_empty_when_no_coverage():
    result = {
        "coverage_found": False,
        "articles": [],
        "source_adapter": "none",
    }
    assert format_coverage_for_prompt(result) == ""


def test_format_coverage_for_prompt_includes_domain_and_title():
    result = {
        "coverage_found": True,
        "source_adapter": "gdelt",
        "articles": [
            {
                "title": "Test headline",
                "domain": "reuters.com",
                "seendate": "2026-03-31T00:00:00Z",
                "language": "English",
            },
        ],
    }
    out = format_coverage_for_prompt(result)
    assert "reuters.com" in out
    assert "Test headline" in out


def test_extract_query_terms_excludes_author():
    from comparative_coverage import extract_query_terms

    terms = extract_query_terms(_sample_article())
    core = " ".join(terms["core_entities"]).lower()
    assert "pat reporter" not in core
