"""
revision_tracker.py

Detects when a named subject has made claims that contradict or revise
claims found in the current article. Uses NewsAPI + GDELT search and Claude.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def _anthropic_key() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def _newsapi_key() -> str:
    return (os.environ.get("NEWSAPI_KEY") or "").strip()


def _claude_model() -> str:
    return (os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514").strip()


async def find_claim_revisions(
    subject: str,
    claim_text: str,
    claim_date: str,
    session: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """
    Search for prior or subsequent statements by `subject` that contradict
    or revise `claim_text`. Returns list of revision objects.
    """
    if not _anthropic_key():
        return []

    search_results = await _search_for_prior_statements(subject, claim_text, session)
    if not search_results:
        return []

    revisions = await asyncio.to_thread(
        _identify_revisions_sync,
        subject,
        claim_text,
        claim_date,
        search_results,
    )
    return revisions if isinstance(revisions, list) else []


async def _search_for_prior_statements(
    subject: str,
    claim_text: str,
    session: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Search NewsAPI and GDELT for past statements. Returns article-shaped dicts."""
    results: list[dict[str, Any]] = []

    claim_words = [
        w
        for w in claim_text.split()
        if len(w) > 4
        and w.lower()
        not in {
            "would",
            "should",
            "could",
            "about",
            "their",
            "there",
            "where",
            "which",
            "while",
            "these",
            "those",
            "after",
            "before",
            "being",
            "every",
        }
    ]
    key_words = " ".join(claim_words[:4])
    query = f'"{subject}" {key_words}'[:150]

    key = _newsapi_key()
    if key:
        try:
            resp = await session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "apiKey": key,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 10,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                articles = resp.json().get("articles") or []
                for a in articles:
                    if not isinstance(a, dict):
                        continue
                    src = a.get("source")
                    src_name = ""
                    if isinstance(src, dict):
                        src_name = str(src.get("name") or "").strip()
                    elif isinstance(src, str):
                        src_name = src.strip()
                    results.append(
                        {
                            "title": a.get("title", "") or "",
                            "url": a.get("url", "") or "",
                            "published_at": a.get("publishedAt", "") or "",
                            "source": src_name,
                            "description": a.get("description", "") or "",
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[REVISION] NewsAPI search failed: %s", exc)

    if len(results) < 5:
        try:
            gdelt_query = quote_plus(f"{subject} {key_words}")
            gdelt_url = (
                f"{GDELT_DOC_API}?query={gdelt_query}&mode=artlist&maxrecords=10"
                f"&format=json&sort=DateDesc&timespan=90d"
            )
            resp = await session.get(gdelt_url, timeout=12.0)
            if resp.status_code == 200:
                data = resp.json()
                for a in data.get("articles") or []:
                    if not isinstance(a, dict):
                        continue
                    results.append(
                        {
                            "title": a.get("title", "") or "",
                            "url": a.get("url", "") or "",
                            "published_at": a.get("seendate", "") or "",
                            "source": a.get("domain", "") or "",
                            "description": "",
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[REVISION] GDELT revision search failed: %s", exc)

    return results[:12]


def _identify_revisions_sync(
    subject: str,
    claim_text: str,
    claim_date: str,
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ask Claude whether search results show a revision or contradiction."""
    import anthropic

    lines: list[str] = []
    for r in search_results:
        pa = r.get("published_at") or ""
        head = pa[:10] if len(pa) >= 10 else (pa or "unknown date")
        src = r.get("source") or ""
        if isinstance(src, dict):
            src = str(src.get("name") or "")
        desc = (r.get("description") or "")[:100]
        lines.append(
            f"- [{head}] {src}: \"{r.get('title', '')}\" "
            f"({r.get('url', '')}) {desc}"
        )
    articles_text = "\n".join(lines)

    prompt = f"""You are analyzing whether a public figure has changed their stated position.

SUBJECT: {subject}
CURRENT CLAIM (from article dated {claim_date}):
"{claim_text}"

RELATED COVERAGE FOUND:
{articles_text}

Task: Identify any cases where {subject} made a DIFFERENT, CONTRADICTORY, or REVISED
statement about the same topic — either before or after the current claim.

For each revision found, return a JSON object. If no revision is found, return [].

Return JSON array only — no explanation, no markdown:
[
  {{
    "revision_type": "REVERSED" or "SOFTENED" or "STRENGTHENED" or "CLARIFIED" or "CONTRADICTED" or "UNKNOWN",
    "original_claim": "exact or close paraphrase of the earlier/later claim",
    "original_date": "YYYY-MM-DD or 'unknown'",
    "original_url": "url from the articles list above, or empty string",
    "original_source": "outlet name",
    "revised_claim": "the current claim or the newer contradicting claim",
    "revised_date": "{claim_date}",
    "revised_url": "",
    "revised_source": "from current article",
    "gap_description": "e.g. '14 days later', '3 months earlier', 'same week'",
    "significance": "one sentence: why this revision matters to this story"
  }}
]

Rules:
- Only return revisions you can support with the articles listed above
- Do not invent claims not evidenced by the articles
- A "REVERSED" revision means the subject explicitly contradicted themselves
- A "SOFTENED" revision means they walked back or weakened a prior claim
- A "STRENGTHENED" revision means they doubled down or escalated
- A "CLARIFIED" revision means they added nuance that changes the meaning
- A "CONTRADICTED" revision means the documented record contradicts their claim
- If no clear revision exists, return []
"""

    try:
        client = anthropic.Anthropic(api_key=_anthropic_key())
        msg = client.messages.create(
            model=_claude_model(),
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        block = msg.content[0]
        text = getattr(block, "text", "") or ""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
        text = text.strip()
        result = json.loads(text)
        if not isinstance(result, list):
            return []
        out: list[dict[str, Any]] = []
        for item in result:
            if isinstance(item, dict):
                out.append(item)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[REVISION] Claude revision check failed: %s", exc)
        return []
