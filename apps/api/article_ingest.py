"""Fetch and extract plain text from a news article URL."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from journalist_byline_normalize import (
    author_field_needs_resolution,
    normalize_journalist_display_name,
)

_BYLINE_CSS_SELECTORS = (
    ".byline",
    ".author-name",
    ".contributor-name",
    '[data-testid="byline"]',
    ".ArticleHeader-byline",
    "p.byline",
    ".article__byline",
)

_META_FIRST_PASS = (
    {"name": re.compile(r"^author$", re.I)},
    {"property": re.compile(r"^article:author$", re.I)},
    {"name": re.compile(r"^byl$", re.I)},
)

_META_EXTENDED = (
    {"property": re.compile(r"^og:article:author$", re.I)},
    {"name": re.compile(r"^twitter:creator$", re.I)},
    {"name": re.compile(r"^parsely-author$", re.I)},
    {"name": re.compile(r"^sailthru\.author$", re.I)},
    {"name": re.compile(r"^dc\.creator$", re.I)},
    {"name": re.compile(r"^author$", re.I)},
    {"property": re.compile(r"^article:author$", re.I)},
)


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


def _meta_content(soup: BeautifulSoup, attrs: dict[str, Any]) -> str | None:
    m = soup.find("meta", attrs=attrs)
    if not m:
        return None
    c = m.get("content")
    if c is None or not str(c).strip():
        return None
    return str(c).strip()


def _meta_author_first_pass(soup: BeautifulSoup) -> str | None:
    for attrs in _META_FIRST_PASS:
        s = _meta_content(soup, attrs)
        if s:
            return s
    return None


def _meta_author_extended(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for attrs in _META_EXTENDED:
        s = _meta_content(soup, attrs)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _clean_byline_text(s: str) -> str:
    t = re.sub(r"\s+", " ", s).strip()
    t = re.sub(r"^(by|from)\s+", "", t, flags=re.I)
    for sep in ("|", "·", "•"):
        if sep in t:
            t = t.split(sep)[0].strip()
    return t[:400]


def _author_value_to_strings(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        s = val.strip()
        return [s] if s else []
    if isinstance(val, list):
        acc: list[str] = []
        for x in val:
            acc.extend(_author_value_to_strings(x))
        return acc
    if isinstance(val, dict):
        if "name" in val:
            n = val.get("name")
            if isinstance(n, str) and n.strip():
                return [n.strip()]
            if isinstance(n, list):
                return [str(x).strip() for x in n if isinstance(x, (str, int, float)) and str(x).strip()]
        if "url" in val and not val.get("name"):
            return _author_value_to_strings(val.get("url"))
        return []
    return []


def _ld_collect_author_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        if "@graph" in obj:
            for g in obj["@graph"]:
                out.extend(_ld_collect_author_strings(g))
        if "mainEntity" in obj:
            out.extend(_ld_collect_author_strings(obj["mainEntity"]))
        for key in ("author", "creator"):
            if key in obj:
                out.extend(_author_value_to_strings(obj[key]))
    elif isinstance(obj, list):
        for it in obj:
            out.extend(_ld_collect_author_strings(it))
    return out


def _json_ld_author_strings(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for s in _ld_collect_author_strings(data):
            s = str(s).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _rel_author_strings(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        rel = tag.get("rel")
        if rel is None:
            continue
        rel_parts = rel if isinstance(rel, list) else str(rel).split()
        if "author" not in rel_parts:
            continue
        t = tag.get_text(separator=" ", strip=True)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    for tag in soup.find_all("link", href=True):
        rel = tag.get("rel")
        if rel is None:
            continue
        rel_parts = rel if isinstance(rel, list) else str(rel).split()
        if "author" not in rel_parts:
            continue
        tit = tag.get("title")
        if tit and str(tit).strip():
            t = str(tit).strip()
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def _byline_css_strings(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for sel in _BYLINE_CSS_SELECTORS:
        try:
            el = soup.select_one(sel)
        except Exception:  # noqa: BLE001
            continue
        if not el:
            continue
        t = el.get_text(separator=" ", strip=True)
        if not t:
            continue
        t = _clean_byline_text(t)
        if t and len(t) > 1 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _pick_resolved_author(candidates: list[str]) -> str | None:
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if not c:
            continue
        cc = _clean_byline_text(c)
        if not cc or cc in seen:
            continue
        seen.add(cc)
        ordered.append(cc)

    for c in ordered:
        if not author_field_needs_resolution(c):
            return c

    for c in ordered:
        if author_field_needs_resolution(c):
            norm, _ = normalize_journalist_display_name(c)
            if norm:
                return norm
    return None


def resolve_article_author(soup: BeautifulSoup, initial: str | None) -> str | None:
    """
    Prefer a human byline from metadata/HTML/JSON-LD; normalize URL-only values to slug names.
    """
    if initial and not author_field_needs_resolution(initial):
        return initial.strip()

    candidates: list[str] = []
    # Prefer structured / visible bylines before extended meta (often duplicate author profile URLs).
    candidates.extend(_json_ld_author_strings(soup))
    candidates.extend(_rel_author_strings(soup))
    candidates.extend(_byline_css_strings(soup))
    candidates.extend(_meta_author_extended(soup))
    if initial:
        candidates.append(initial)

    picked = _pick_resolved_author(candidates)
    if picked:
        return picked
    if initial:
        norm, _ = normalize_journalist_display_name(initial)
        if norm:
            return norm
    return None


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

    initial_author = _meta_author_first_pass(soup)
    author = resolve_article_author(soup, initial_author)

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
