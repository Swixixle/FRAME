# Congress.gov API — voting records on campaign finance legislation

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)
_MISSING_KEY_LOGGED = False

BASE = "https://api.congress.gov/v3"

_CF_SEARCH_QUERIES = (
    "DISCLOSE Act",
    "campaign finance",
    "Citizens United",
    "bipartisan campaign reform",
)

# Senators voting NO on DISCLOSE Act Senate cloture, July 27, 2010 (57–41).
# Primary source: Senate roll call vote 111-2-220.
DISCLOSE_ACT_VOTE_2010_SOURCE_URL = (
    "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1112/vote_111_2_00220.htm"
)

DISCLOSE_ACT_HOUSE_VOTE_2010_SOURCE_URL = "https://clerk.house.gov/evs/2010/roll391.xml"

DISCLOSE_ACT_HOUSE_NO_VOTES_2010: list[dict[str, Any]] = [
    # Source: clerk.house.gov/evs/2010/roll391.xml
    # House Roll Call 391, June 24 2010, H.R. 5175
    # 206 members voted NAY — top recipients of post-Citizens United PAC money seeded here
    {"name": "John Boehner", "state": "OH", "party": "R", "chamber": "house"},
    {"name": "Eric Cantor", "state": "VA", "party": "R", "chamber": "house"},
    {"name": "Kevin McCarthy", "state": "CA", "party": "R", "chamber": "house"},
    {"name": "Paul Ryan", "state": "WI", "party": "R", "chamber": "house"},
    {"name": "Michele Bachmann", "state": "MN", "party": "R", "chamber": "house"},
    {"name": "Darrell Issa", "state": "CA", "party": "R", "chamber": "house"},
    {"name": "Mike Pence", "state": "IN", "party": "R", "chamber": "house"},
    {"name": "Pete Sessions", "state": "TX", "party": "R", "chamber": "house"},
    {"name": "Lamar Smith", "state": "TX", "party": "R", "chamber": "house"},
    {"name": "Spencer Bachus", "state": "AL", "party": "R", "chamber": "house"},
]

DISCLOSE_ACT_NO_VOTES_2010: list[dict[str, Any]] = [
    {"name": "Mitch McConnell", "state": "KY", "party": "R", "chamber": "senate"},
    {"name": "John Cornyn", "state": "TX", "party": "R", "chamber": "senate"},
    {"name": "John Thune", "state": "SD", "party": "R", "chamber": "senate"},
    {"name": "Jon Kyl", "state": "AZ", "party": "R", "chamber": "senate"},
    {"name": "John Barrasso", "state": "WY", "party": "R", "chamber": "senate"},
    {"name": "Lamar Alexander", "state": "TN", "party": "R", "chamber": "senate"},
    {"name": "Roy Blunt", "state": "MO", "party": "R", "chamber": "senate"},
    {"name": "John Boozman", "state": "AR", "party": "R", "chamber": "senate"},
    {"name": "Richard Burr", "state": "NC", "party": "R", "chamber": "senate"},
    {"name": "Saxby Chambliss", "state": "GA", "party": "R", "chamber": "senate"},
]


def _api_key() -> str | None:
    import os

    k = (os.environ.get("CONGRESS_API_KEY") or "").strip()
    return k or None


def _warn_no_key() -> None:
    global _MISSING_KEY_LOGGED
    if _api_key() is None and not _MISSING_KEY_LOGGED:
        _LOG.warning("CONGRESS_API_KEY not set; Congress.gov calls return empty results.")
        _MISSING_KEY_LOGGED = True


def _bill_type_for_url(bill_type: str) -> str:
    t = (bill_type or "").strip().lower()
    return t if t else "hr"


def _normalize_bill_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    b = raw.get("bill") if isinstance(raw.get("bill"), dict) else raw
    if not isinstance(b, dict):
        return None
    cong = b.get("congress")
    try:
        congress_i = int(cong) if cong is not None else 0
    except (TypeError, ValueError):
        congress_i = 0
    btype = str(b.get("type") or b.get("billType") or "").strip()
    num_raw = b.get("number") or b.get("billNumber")
    number_i = 0
    if num_raw is not None:
        s = str(num_raw).strip()
        if s.isdigit():
            number_i = int(s)
        else:
            m_num = re.search(r"(\d+)", s)
            number_i = int(m_num.group(1)) if m_num else 0
    title = str(b.get("title") or b.get("latestTitle") or "").strip()
    intro = str(b.get("introducedDate") or b.get("introducedOn") or "").strip()
    la = b.get("latestAction") if isinstance(b.get("latestAction"), dict) else {}
    lact_date = str(la.get("actionDate") or "").strip()
    lact_text = str(la.get("text") or "").strip()
    latest_action = f"{lact_date} — {lact_text}".strip(" —") if (lact_date or lact_text) else ""
    url = str(
        b.get("congressdotgov_url")
        or b.get("congressDotGovUrl")
        or b.get("url")
        or b.get("congressionalUrl")
        or ""
    ).strip()
    if url.startswith("/"):
        url = f"https://www.congress.gov{url}"
    bill_id = ""
    if congress_i and btype and number_i:
        bill_id = f"{congress_i}-{btype}-{number_i}".lower()
    elif title:
        bill_id = re.sub(r"\W+", "-", title.lower())[:120]
    return {
        "bill_id": bill_id,
        "title": title,
        "congress": congress_i,
        "type": btype,
        "introduced_date": intro,
        "latest_action": latest_action,
        "url": url,
        "source_type": "legislation",
    }


async def _congress_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    _warn_no_key()
    key = _api_key()
    if key is None:
        return {}
    p = dict(params or {})
    p["format"] = "json"
    p["api_key"] = key
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.get(f"{BASE}{path}", params=p)
            if r.status_code == 401:
                p2 = {k: v for k, v in p.items() if k != "api_key"}
                r = await client.get(
                    f"{BASE}{path}",
                    params=p2,
                    headers={"X-API-Key": key},
                )
            r.raise_for_status()
            data = r.json()
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("Congress.gov GET %s failed: %s", path, exc)
        return {}


def _bills_from_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("bills") or data.get("results") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = _normalize_bill_row(item)
        if row and row.get("title"):
            out.append(row)
    return out


async def search_legislation(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        q = (query or "").strip()
        if not q:
            return []
        lim = min(max(limit, 1), 50)
        data = await _congress_get("/bill", {"query": q, "limit": lim})
        return _bills_from_payload(data)[:lim]
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("search_legislation failed: %s", exc)
        return []


async def get_bill_votes(congress: int, bill_type: str, bill_number: int) -> list[dict[str, Any]]:
    try:
        if not _api_key():
            _warn_no_key()
            return []
        bt = _bill_type_for_url(bill_type)
        path = f"/bill/{int(congress)}/{bt}/{int(bill_number)}/votes"
        data = await _congress_get(path, {"limit": 100})
        votes_raw = data.get("votes") or []
        if not isinstance(votes_raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in votes_raw:
            v = item.get("vote") if isinstance(item.get("vote"), dict) else item
            if not isinstance(v, dict):
                continue
            chamber = str(v.get("chamber") or "").strip()
            res = str(v.get("result") or "").strip()
            vdate = str(
                v.get("date")
                or v.get("startDate")
                or v.get("voteCastDate")
                or v.get("updateDate")
                or ""
            ).strip()
            yes = v.get("yesTotals") or v.get("yeaTotal") or v.get("yes")
            no = v.get("noTotals") or v.get("nayTotal") or v.get("no")
            nv = v.get("notVotingTotals") or v.get("presentTotal") or v.get("notVoting")
            try:
                total_yes = int(yes) if yes is not None else 0
            except (TypeError, ValueError):
                total_yes = 0
            try:
                total_no = int(no) if no is not None else 0
            except (TypeError, ValueError):
                total_no = 0
            try:
                total_not = int(nv) if nv is not None else 0
            except (TypeError, ValueError):
                total_not = 0
            vote_url = str(
                v.get("url") or v.get("congressDotGovUrl") or v.get("congressdotgov_url") or ""
            ).strip()
            if vote_url.startswith("/"):
                vote_url = f"https://www.congress.gov{vote_url}"
            out.append(
                {
                    "vote_date": vdate,
                    "chamber": chamber,
                    "result": res,
                    "total_yes": total_yes,
                    "total_no": total_no,
                    "total_not_voting": total_not,
                    "url": vote_url,
                    "source_type": "congressional_vote",
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("get_bill_votes failed: %s", exc)
        return []


async def search_member(name: str) -> list[dict[str, Any]]:
    try:
        q = (name or "").strip()
        if not q:
            return []
        data = await _congress_get("/member", {"query": q, "limit": 5})
        members_raw = data.get("members") or []
        if not isinstance(members_raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in members_raw:
            m = item.get("member") if isinstance(item.get("member"), dict) else item
            if not isinstance(m, dict):
                continue
            bg = str(m.get("bioguideId") or m.get("bioguide_id") or "").strip()
            disp = str(
                m.get("name")
                or m.get("directOrderName")
                or m.get("honorificName")
                or ""
            ).strip()
            party = str(m.get("partyName") or m.get("party") or "").strip()
            state = str(m.get("state") or "").strip()
            terms = m.get("terms") or m.get("termsOfService")
            served_from: str | None = None
            if isinstance(terms, dict):
                item_list = terms.get("item")
                if isinstance(item_list, list) and item_list:
                    first = item_list[0] if isinstance(item_list[0], dict) else {}
                    served_from = str(first.get("startYear") or first.get("startDate") or "") or None
            url = str(m.get("url") or m.get("memberUrl") or "").strip()
            if url.startswith("/"):
                url = f"https://www.congress.gov{url}"
            out.append(
                {
                    "bioguide_id": bg,
                    "name": disp,
                    "party": party,
                    "state": state,
                    "served_from": served_from,
                    "url": url,
                }
            )
        return out[:5]
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("search_member failed: %s", exc)
        return []


async def get_campaign_finance_votes() -> list[dict[str, Any]]:
    try:
        if not _api_key():
            _warn_no_key()
            return []
        lists = await asyncio.gather(*[search_legislation(sq, limit=5) for sq in _CF_SEARCH_QUERIES])
        merged: dict[str, dict[str, Any]] = {}
        for lst in lists:
            for row in lst:
                bid = str(row.get("bill_id") or "").strip()
                if not bid:
                    continue
                merged.setdefault(bid, row)
        return list(merged.values())
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("get_campaign_finance_votes failed: %s", exc)
        return []
