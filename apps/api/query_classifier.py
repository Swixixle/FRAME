"""
Query classifier — determines query type and extracts structured parameters
so the right data source is used for each query.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Any

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

CURRENT_EVENT_TRIGGERS = {
    "today",
    "tonight",
    "now",
    "currently",
    "latest",
    "recent",
    "happening",
    "going on",
    "right now",
    "this week",
    "this month",
    "breaking",
    "live",
    "ongoing",
}

CURRENT_EVENT_TRIGGERS_WORD = {
    "just",
    "new",
}

HISTORICAL_TRIGGERS_PHRASE = {
    "yesterday",
    "last week",
    "last month",
    "last year",
    "back in",
    "at the time",
    "that day",
    "that week",
}

HISTORICAL_TRIGGERS_WORD = {
    "ago",
    "previously",
    "former",
    "past",
    "during",
    "when",
}


def _lower_has_phrase(lower: str, phrase: str) -> bool:
    return phrase in lower


def _lower_has_any_phrase(lower: str, phrases: set[str]) -> bool:
    return any(_lower_has_phrase(lower, p) for p in phrases)


def _lower_has_word_token(lower: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", lower))


def _lower_has_any_word(lower: str, words: set[str]) -> bool:
    return any(_lower_has_word_token(lower, w) for w in words)


def _is_current_event(lower: str) -> bool:
    if _lower_has_any_phrase(lower, CURRENT_EVENT_TRIGGERS):
        return True
    if _lower_has_any_word(lower, CURRENT_EVENT_TRIGGERS_WORD):
        return True
    return False


def _is_historical_tone(lower: str) -> bool:
    if _lower_has_any_phrase(lower, HISTORICAL_TRIGGERS_PHRASE):
        return True
    if _lower_has_any_word(lower, HISTORICAL_TRIGGERS_WORD):
        return True
    return False


def extract_date_range(query: str) -> dict[str, Any] | None:
    q = query.lower().strip()
    now = datetime.now(timezone.utc)

    specific = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})",
        q,
    )
    if not specific:
        specific = re.search(
            r"(\d{1,2})(?:st|nd|rd|th)?\s+"
            r"(january|february|march|april|may|june|july|august|september|october|november|december|"
            r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
            r"\s+(\d{4})",
            q,
        )
        if specific:
            day = int(specific.group(1))
            month = MONTHS[specific.group(2)]
            year = int(specific.group(3))
        else:
            specific = None
    else:
        month = MONTHS[specific.group(1)]
        day = int(specific.group(2))
        year = int(specific.group(3))

    if specific:
        try:
            start = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)
            end = datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)
            return {
                "type": "specific_day",
                "start": start,
                "end": end,
                "label": start.strftime("%B %d, %Y"),
            }
        except ValueError:
            pass

    month_year = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"(?:\s+of)?\s+(\d{4})",
        q,
    )
    if month_year:
        month = MONTHS[month_year.group(1)]
        year = int(month_year.group(2))
        try:
            start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
            last_day = calendar.monthrange(year, month)[1]
            end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
            return {
                "type": "month",
                "start": start,
                "end": end,
                "label": start.strftime("%B %Y"),
            }
        except ValueError:
            pass

    year_only = re.search(r"\b(20\d{2})\b", q)
    if year_only:
        year = int(year_only.group(1))
        if 2000 <= year <= 2100:
            try:
                start = datetime(year, 1, 1, tzinfo=timezone.utc)
                end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
                return {
                    "type": "year",
                    "start": start,
                    "end": end,
                    "label": str(year),
                }
            except ValueError:
                pass

    if "last week" in q:
        start = now - timedelta(days=7)
        return {"type": "relative", "start": start, "end": now, "label": "last week"}
    if "last month" in q:
        start = now - timedelta(days=30)
        return {"type": "relative", "start": start, "end": now, "label": "last month"}
    if "yesterday" in q:
        day = now - timedelta(days=1)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = day.replace(hour=23, minute=59, second=59, microsecond=0)
        return {
            "type": "specific_day",
            "start": start,
            "end": end,
            "label": day.strftime("%B %d, %Y"),
        }

    return None


def classify_query(query: str) -> dict[str, Any]:
    q = query.strip()
    lower = q.lower()

    date_range = extract_date_range(q)

    stop = {
        "tell",
        "me",
        "about",
        "what",
        "is",
        "are",
        "was",
        "were",
        "the",
        "a",
        "an",
        "and",
        "or",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "how",
        "why",
        "when",
        "who",
        "where",
        "happening",
        "going",
        "today",
        "now",
        "latest",
        "recent",
        "news",
        "story",
        "give",
        "show",
        "find",
        "search",
        "summarize",
        "describe",
        "during",
        "that",
        "this",
        "from",
        "between",
        "through",
        "march",
        "january",
        "february",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
        "st",
        "nd",
        "rd",
        "th",
        "last",
        "week",
        "month",
        "year",
        "yesterday",
        "ago",
        "back",
        "time",
    }
    words = re.findall(r"[a-zA-Z']+", lower)
    search_terms = [w for w in words if w not in stop and len(w) > 2]
    search_terms = [w for w in search_terms if not re.match(r"^20\d{2}$", w)]

    entity_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", q)
    entity = entity_match.group(1) if entity_match else None

    is_current = _is_current_event(lower)
    is_historical = bool(date_range) or _is_historical_tone(lower)

    gdelt_timespan = "7d"
    if is_historical and date_range:
        if date_range["type"] in ("month", "year"):
            query_type = "entity_timeline"
            source = "gdelt_timeline"
        else:
            query_type = "historical"
            source = "gdelt"
    elif is_current or not is_historical:
        query_type = "current"
        source = "rss"
    else:
        query_type = "current"
        source = "rss"

    return {
        "type": query_type,
        "query": q,
        "search_terms": search_terms[:6],
        "entity": entity,
        "date_range": date_range,
        "source": source,
        "gdelt_timespan": gdelt_timespan,
    }
