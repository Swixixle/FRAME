"""
Pipeline-only normalization for article bylines passed to journalist investigations.

Does not alter API payloads — callers use the returned display string only for
``build_journalist_investigation_record`` / Layer B, leaving ``article["author"]`` unchanged.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_RE_HTML_EXT = re.compile(r"\.(?:html?|php|aspx)$", re.IGNORECASE)
_RE_HTTP_IN_TEXT = re.compile(r"https?://[^\s<>\"\'\[\]]+", re.IGNORECASE)


def normalize_journalist_display_name(author_raw: Any) -> tuple[str, str | None]:
    """
    Returns ``(display_name_for_investigations, full_comma_separated_byline_or_none)``.

    * ``None`` / blank author → ``("", None)`` — never invent a name from a URL.
    * Comma-separated list → first author only for investigations; full string in tuple[1].
    * URL (``http``/``https``) or string containing ``/author/`` → last path segment,
      hyphen/underscore split, title-cased words (e.g. ``bassem-mroue`` → ``Bassem Mroue``).
    """
    raw = _coerce_author_raw(author_raw)
    if not raw:
        return "", None

    full_byline: str | None = None
    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) > 1:
            full_byline = raw
        raw = parts[0] if parts else raw

    if _looks_like_author_url(raw):
        converted = _name_from_url_or_author_path(raw)
        if not converted:
            extracted = _first_http_url_in_string(raw)
            if extracted:
                converted = _name_from_url_or_author_path(extracted)
        if converted:
            raw = converted

    return raw.strip(), full_byline


def _strip_invisible(s: str) -> str:
    return (
        s.replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .strip()
    )


def _stringish(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, str):
        out = _strip_invisible(val)
        return out if out else None
    return None


def _coerce_author_raw(author_raw: Any) -> str:
    """Unwrap list/tuple/JSON-LD-shaped dicts; strip BOM/invisible chars."""
    if author_raw is None:
        return ""
    if isinstance(author_raw, (list, tuple)):
        if not author_raw:
            return ""
        return _coerce_author_raw(author_raw[0])
    if isinstance(author_raw, dict):
        name_v = author_raw.get("name")
        url_v = author_raw.get("url")
        same_v = author_raw.get("sameAs") or author_raw.get("@id")
        if isinstance(name_v, list) and name_v:
            name_v = name_v[0]
        if isinstance(url_v, list) and url_v:
            url_v = url_v[0]
        if isinstance(same_v, list) and same_v:
            same_v = same_v[0]

        nm = _stringish(name_v)
        if nm and not _looks_like_author_url(nm):
            return nm
        u = _stringish(url_v) or _stringish(same_v)
        if u:
            return u
        if nm:
            return nm
        return ""
    return _strip_invisible(str(author_raw).strip())


def _first_http_url_in_string(s: str) -> str | None:
    m = _RE_HTTP_IN_TEXT.search(s)
    if not m:
        return None
    return m.group(0).rstrip(".,);]}")


def _looks_like_author_url(s: str) -> bool:
    sl = s.lower()
    if sl.startswith("http://") or sl.startswith("https://"):
        return True
    return "/author/" in s


def _title_case_token(w: str) -> str:
    if not w:
        return ""
    return w[0].upper() + w[1:].lower() if len(w) > 1 else w.upper()


def _name_from_url_or_author_path(s: str) -> str:
    s2 = _strip_invisible(s)
    path = ""
    low = s2.lower()
    if low.startswith("http://") or low.startswith("https://"):
        try:
            path = (urlparse(s2).path or "").strip("/")
        except Exception:  # noqa: BLE001
            return ""
    else:
        idx = s2.lower().find("/author/")
        if idx < 0:
            return ""
        tail = s2[idx + len("/author/") :].split("?")[0].split("#")[0].strip("/")
        path = f"author/{tail}" if tail else ""

    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return ""
    slug = segments[-1]
    slug = _RE_HTML_EXT.sub("", slug)
    slug = slug.rstrip(".,);]}\"'")
    if not slug or slug.lower() in ("author", "www", "index"):
        return ""
    words = [w for w in re.split(r"[-_]+", slug) if w]
    if not words:
        return ""
    return " ".join(_title_case_token(w) for w in words)
