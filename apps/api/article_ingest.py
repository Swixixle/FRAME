"""Fetch and extract plain text from a news article URL."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


def _domain_fallback_title(url: str) -> str:
    """Readable fallback when title extraction failed or yielded junk."""
    try:
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        name = domain.split(".")[0].title() if domain else "Source"
        return f"Investigation — {name}"
    except Exception:  # noqa: BLE001
        return "Untitled investigation"


def sanitize_title(raw_title: str | None, url: str) -> str:
    """Clean display title; reject site-suffix-only junk (e.g. '- YouTube')."""
    if not raw_title or not str(raw_title).strip():
        return _domain_fallback_title(url)

    cleaned = str(raw_title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if re.match(r"^[-|·•]\s*\w", cleaned):
        return _domain_fallback_title(url)
    if len(cleaned) < 8 and re.search(
        r"(youtube|cnn|bbc|reuters|twitter|facebook)", cleaned, re.I
    ):
        return _domain_fallback_title(url)

    return cleaned


def fetch_article(url: str, timeout: int = 15) -> dict[str, Any]:
    """
    Fetch and clean article text from a URL.
    Returns dict with: url, title, publication, author (optional), text, word_count,
    truncated, fetch_error
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Frame/1.0; +https://frame-2yxu.onrender.com)"
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return {
            "url": url,
            "title": None,
            "publication": None,
            "text": None,
            "word_count": 0,
            "truncated": False,
            "fetch_error": str(e),
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", {"class": re.compile(r"article|story|content|body", re.I)})
        or soup.body
    )

    text = container.get_text(separator=" ", strip=True) if container else ""
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    truncated = len(words) > 8000
    text = " ".join(words[:8000])

    publication = urlparse(url).netloc.replace("www.", "")

    author: str | None = None
    for attrs in (
        {"name": re.compile(r"^author$", re.I)},
        {"property": re.compile(r"^article:author$", re.I)},
        {"name": re.compile(r"^byl$", re.I)},
    ):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            author = str(m.get("content")).strip() or None
            if author:
                break

    return {
        "url": url,
        "title": sanitize_title(title, url),
        "publication": publication,
        "author": author,
        "text": text,
        "word_count": len(words),
        "truncated": truncated,
        "fetch_error": None,
    }
