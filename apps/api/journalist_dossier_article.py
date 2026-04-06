"""
Journalist dossier enrichment for article_analysis receipts (alongside existing flow).
Uses GDELT for byline-adjacent counts and OpenFEC schedule A for name-match donations (unverified).
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import httpx

from gdelt_adapter import search_gdelt

logger = logging.getLogger(__name__)

_STOP = frozenset(
    "the a an and or for to of in on at by from with is are was were be been being".split()
)

_ORG_HINT = re.compile(
    r"\b(inc\.?|llc|ltd\.?|corp\.?|corporation|company|co\.|association|foundation|"
    r"university|college|institute|department|ministry|agency|hospital|group|partners|holdings)\b",
    re.I,
)


def _domain_from_url(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:  # noqa: BLE001
        return ""


def _topic_keywords(topic: str | None, limit: int = 4) -> list[str]:
    if not topic:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", topic or "")
    out: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in _STOP or len(lw) < 3:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _titles_from_gdelt_rows(rows: list[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for r in rows:
        if isinstance(r, dict):
            t = str(r.get("title") or "").strip()
            if t:
                titles.append(t)
    return titles


def _beat_history_from_titles(titles: list[str], top_n: int = 3) -> list[dict[str, Any]]:
    """Lightweight pseudo-beats: most common significant bigrams across titles."""
    bigrams: Counter[str] = Counter()
    for t in titles:
        toks = [x.lower() for x in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", t)]
        for i in range(len(toks) - 1):
            if toks[i] in _STOP or toks[i + 1] in _STOP:
                continue
            bigrams[f"{toks[i]} {toks[i + 1]}"] += 1
    out: list[dict[str, Any]] = []
    for phrase, n in bigrams.most_common(top_n):
        if len(phrase) < 5:
            continue
        out.append({"topic": phrase.title(), "approx_article_count": int(n)})
    while len(out) < top_n:
        out.append({"topic": "", "approx_article_count": 0})
    return out[:top_n]


def _extract_quote_spans(text: str) -> list[str]:
    """Quoted speech spans — straight and curly double quotes only (apostrophes avoided)."""
    if not (text or "").strip():
        return []
    spans: list[str] = []
    for m in re.finditer(r'"([^"]{2,2000})"', text):
        spans.append(m.group(1))
    for m in re.finditer(r"\u201c([^\u201d]{2,2000})\u201d", text):
        spans.append(m.group(1))
    return spans


def _name_in_any_quote_span(name: str, spans: list[str]) -> bool:
    nl = name.strip().lower()
    if len(nl) < 4:
        return False
    for sp in spans:
        if nl in (sp or "").lower():
            return True
    return False


def _looks_like_person_name(label: str) -> bool:
    s = (label or "").strip()
    if len(s) < 5 or _ORG_HINT.search(s):
        return False
    parts = s.split()
    if len(parts) < 2 or len(parts) > 5:
        return False
    for p in parts:
        if not re.match(r"^[A-Za-z][A-Za-z'\-.]*$", p):
            return False
    return True


def _person_labels_from_named_entities(raw: list[Any]) -> list[str]:
    """Strings or {type: PERSON, name: ...}; de-dup preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for e in raw or []:
        if isinstance(e, dict):
            t = str(e.get("type") or e.get("entity_type") or "").strip().upper()
            n = e.get("name") or e.get("text") or e.get("entity")
            if not n:
                continue
            if t != "PERSON":
                continue
            lab = str(n).strip()
        elif isinstance(e, str):
            lab = e.strip()
            if not _looks_like_person_name(lab):
                continue
        else:
            continue
        key = lab.lower()
        if key not in seen:
            seen.add(key)
            out.append(lab)
    return out


def _pick_quoted_person_sources(
    article_text: str | None,
    named_entities: list[Any] | None,
    *,
    author_name: str,
    limit: int = 3,
) -> list[str]:
    spans = _extract_quote_spans(article_text or "")
    if not spans:
        return []
    labels = _person_labels_from_named_entities(named_entities)
    author_key = (author_name or "").strip().lower()
    picked: list[str] = []
    for lab in labels:
        if author_key and lab.strip().lower() == author_key:
            continue
        if not _name_in_any_quote_span(lab, spans):
            continue
        picked.append(lab)
        if len(picked) >= limit:
            break
    return picked


def _fec_one_line_note(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    top = rows[0]
    amt = top.get("amount")
    try:
        amt_s = f"${float(amt):,.0f}" if amt is not None else "amount n/a"
    except (TypeError, ValueError):
        amt_s = str(amt) if amt is not None else "amount n/a"
    recip = top.get("recipient_committee") or "committee unknown"
    dt = top.get("contribution_date") or ""
    tail = f" — {len(rows)} OpenFEC Schedule A row(s), name-only match (unverified identity)"
    base = f"{amt_s} to {recip}" + (f" ({dt})" if dt else "")
    return base + tail


def _fetch_fec_schedule_a_individual(contributor_name: str, limit: int = 8) -> list[dict[str, Any]]:
    key = (os.environ.get("FEC_API_KEY") or "DEMO_KEY").strip()
    if not contributor_name or len(contributor_name.strip()) < 3:
        return []
    try:
        resp = httpx.get(
            "https://api.open.fec.gov/v1/schedules/schedule_a/",
            params={
                "api_key": key,
                "contributor_name": contributor_name.strip()[:100],
                "per_page": limit,
                "sort": "-contribution_receipt_date",
                "two_year_transaction_period": 2024,
            },
            timeout=20.0,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = data.get("results") or []
        out: list[dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            amt = r.get("contribution_receipt_amount")
            out.append(
                {
                    "match_confidence": "name_only_unverified",
                    "amount": amt,
                    "recipient_committee": r.get("committee_name") or r.get("committee", {}).get("name")
                    if isinstance(r.get("committee"), dict)
                    else r.get("committee_name"),
                    "contribution_date": r.get("contribution_receipt_date"),
                    "contributor_name_reported": r.get("contributor_name"),
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("[journalist_dossier] FEC schedule_a: %s", exc)
        return []


def _quoted_sources_payload(
    article_text: str | None,
    named_entities: list[Any] | None,
    author_name: str,
) -> list[dict[str, Any]]:
    names = _pick_quoted_person_sources(
        article_text,
        named_entities,
        author_name=author_name,
        limit=3,
    )
    out: list[dict[str, Any]] = []
    for nm in names:
        try:
            rows = _fetch_fec_schedule_a_individual(nm, limit=5)
        except Exception:  # noqa: BLE001
            rows = []
        out.append(
            {
                "name": nm,
                "fec_match": bool(rows),
                "fec_note": _fec_one_line_note(rows) if rows else None,
            },
        )
    return out


def build_journalist_dossier_for_article(
    author: str,
    publication: str,
    article_topic: str | None,
    article_url: str,
    article_text: str | None = None,
    named_entities: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Sync builder for asyncio.to_thread. Never raises — returns a partial dossier on failure.
    """
    name = (author or "").strip()
    quoted_sources = _quoted_sources_payload(article_text, named_entities, name)

    if not name:
        if not quoted_sources:
            return {}
        return {
            "quoted_sources": quoted_sources,
            "method_note": (
                "OpenFEC Schedule A on quoted names: name-only matches inside quotation marks; "
                "not identity verification."
            ),
        }

    pub = (publication or "").strip()
    domain = _domain_from_url(article_url)
    q_base = f'"{name}"'
    if pub and pub != domain:
        q_base = f'{q_base} ({pub})'

    byline_rows: list[dict[str, Any]] = []
    try:
        byline_rows = search_gdelt(q_base, timespan="12m", max_records=20, log_empty=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[journalist_dossier] GDELT byline: %s", exc)

    titles = _titles_from_gdelt_rows(byline_rows)
    beat_history = _beat_history_from_titles(titles, 3)

    kws = _topic_keywords(article_topic)
    topic_query = q_base
    if kws:
        topic_query = q_base + " " + " ".join(kws[:3])

    topic_rows: list[dict[str, Any]] = []
    try:
        topic_rows = search_gdelt(topic_query, timespan="24m", max_records=15, log_empty=False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[journalist_dossier] GDELT topic: %s", exc)

    story_count_on_topic = len(topic_rows)
    topic_significant = bool(article_topic and len(article_topic.strip()) > 15 and len(kws) >= 2)
    coverage_gap = topic_significant and story_count_on_topic == 0

    fec = _fetch_fec_schedule_a_individual(name)

    return {
        "display_name": name,
        "outlet": pub or domain or "",
        "beat_history": [b for b in beat_history if b.get("topic")],
        "story_count_on_topic": story_count_on_topic,
        "byline_mentions_approx": len(byline_rows),
        "fec_donations": fec,
        "quoted_sources": quoted_sources,
        "coverage_gap": coverage_gap,
        "method_note": (
            "GDELT byline/topic counts are approximate; journalist and quoted-name FEC rows are "
            "OpenFEC name-only matches, not identity verification."
        ),
    }
