"""
HTTP adapters for Gap 3 routing (sync helpers; call via asyncio.to_thread from FastAPI).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _get_json(url: str) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Frame/1.0 (https://github.com/Swixixle/FRAME)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            status = resp.status
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise
        err_body = e.read().decode()[:400] if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    return status, json.loads(raw)


def fetch_fec_by_name(name: str) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("FEC: empty name")
    fec_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    q = urllib.parse.quote(name.strip())
    cand_url = f"https://api.open.fec.gov/v1/candidates/?q={q}&per_page=3&api_key={fec_key}"
    status, data = _get_json(cand_url)
    if status != 200:
        raise RuntimeError(f"FEC candidate search HTTP {status}")
    results = data.get("results") or []
    if not results:
        return {
            "summary": f"FEC: no candidate rows for “{name}”",
            "candidates": [],
            "sourceUrl": cand_url,
        }
    top = results[0]
    cid = top.get("candidate_id")
    cname = top.get("name") or name
    totals_url = (
        f"https://api.open.fec.gov/v1/candidates/totals/?candidate_id={cid}"
        f"&per_page=10&api_key={fec_key}&sort=-cycle"
    )
    _, totals_data = _get_json(totals_url)
    tr = totals_data.get("results") or []
    cycles = []
    total_receipts = 0.0
    for row in tr[:8]:
        try:
            rec = float(row.get("receipts") or 0)
        except (TypeError, ValueError):
            rec = 0.0
        total_receipts += rec
        cycles.append(
            {
                "cycle": row.get("cycle"),
                "receipts": rec,
                "electionYear": row.get("election_year"),
            },
        )
    summary = f"FEC: {cname} — career cycles retrieved; latest cycles show combined receipts in OpenFEC totals (see adapterData)."
    if cycles:
        latest = cycles[0]
        summary = (
            f"FEC: {cname} — ${latest.get('receipts', 0):,.0f} receipts "
            f"({latest.get('cycle') or 'n/a'} cycle) per OpenFEC totals."
        )
    return {
        "summary": summary,
        "candidateId": cid,
        "candidateName": cname,
        "office": top.get("office_full"),
        "party": top.get("party_full"),
        "cycles": cycles,
        "sourceUrl": totals_url,
        "searchUrl": cand_url,
    }


def fetch_irs990_by_name(name: str) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("990: empty name")
    base = "https://projects.propublica.org/nonprofits/api/v2"
    search_url = f"{base}/search.json?q={urllib.parse.quote(name.strip())}"
    status, data = _get_json(search_url)
    orgs = data.get("organizations") or []
    if not orgs:
        return {
            "summary": f"ProPublica 990: no organizations for “{name}”",
            "organizations": [],
            "sourceUrl": search_url,
        }
    first = orgs[0]
    ein = str(first.get("ein") or "")
    oname = first.get("name") or name
    detail_url = f"{base}/organizations/{ein}.json"
    try:
        _, detail = _get_json(detail_url)
    except Exception:
        detail = {}
    rev = detail.get("filings_with_data") or detail.get("organization") or {}
    summary = f"IRS 990 (ProPublica): {oname} (EIN {ein}) — nonprofit registry match."
    return {
        "summary": summary,
        "ein": ein,
        "name": oname,
        "city": first.get("city"),
        "state": first.get("state"),
        "sourceUrl": detail_url,
        "searchUrl": search_url,
        "detail": detail if isinstance(detail, dict) else {},
    }


def fetch_lda_by_name(name: str) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("LDA: empty name")
    base = "https://lda.senate.gov/api/v1"
    n = name.strip()
    filings_url = f"{base}/filings/?filing_year=2024&filing_type=RR&registrant_name={urllib.parse.quote(n)}&limit=5"
    status, data = _get_json(filings_url)
    filings = data.get("results") or []
    summary = f"Senate LDA: {len(filings)} registration filing(s) (RR, 2024) for registrant search “{n}”."
    if filings:
        f0 = filings[0]
        reg = (f0.get("registrant") or {}).get("name") or "?"
        cli = (f0.get("client") or {}).get("name") or "?"
        summary = f"Senate LDA: {reg} / client {cli} — sample 2024 RR filing."
    return {
        "summary": summary,
        "filingCount": len(filings),
        "filings": filings[:5],
        "sourceUrl": filings_url,
    }


def fetch_wikidata_by_name(name: str) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("Wikidata: empty name")
    q = urllib.parse.quote(name.strip())
    url = (
        f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}"
        f"&language=en&format=json&limit=5"
    )
    status, data = _get_json(url)
    hits = data.get("search") or []
    if not hits:
        return {"summary": f"Wikidata: no entities for “{name}”", "entities": [], "sourceUrl": url}
    top = hits[0]
    label = top.get("label") or name
    eid = top.get("id")
    summary = f"Wikidata: {label} ({eid})"
    return {
        "summary": summary,
        "id": eid,
        "label": label,
        "description": top.get("description"),
        "sourceUrl": f"https://www.wikidata.org/wiki/{eid}",
        "searchUrl": url,
    }


def fetch_congress_bills(query: str) -> dict[str, Any]:
    q = urllib.parse.quote((query or "").strip()[:500])
    if not q:
        raise ValueError("Congress: empty query")
    key = os.environ.get("CONGRESS_API_KEY", "").strip()
    if not key:
        return {
            "summary": "Congress.gov: set CONGRESS_API_KEY (free signup at api.congress.gov) to search bills.",
            "bills": [],
            "sourceUrl": "https://api.congress.gov/",
            "error": "missing_api_key",
        }
    path = f"https://api.congress.gov/v3/bill?query={q}&limit=5&format=json&api_key={urllib.parse.quote(key)}"
    try:
        _, data = _get_json(path)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {
                "summary": "Congress.gov: rate limited (429). Set CONGRESS_API_KEY or retry later.",
                "bills": [],
                "sourceUrl": path,
                "error": "rate_limited",
            }
        raise
    bills_raw = data.get("bills") or data.get("results") or []
    bills: list[dict[str, Any]] = []
    for item in bills_raw[:5]:
        if not isinstance(item, dict):
            continue
        b = item.get("bill") if isinstance(item.get("bill"), dict) else item
        title = b.get("title") or b.get("latestTitle") or ""
        num = b.get("number") or b.get("billNumber") or ""
        cgr = b.get("congress")
        bt = b.get("type") or b.get("billType") or ""
        url = b.get("url") or b.get("congressionalUrl") or ""
        latest = b.get("latestAction") or {}
        lact = latest.get("text") if isinstance(latest, dict) else str(latest)
        bills.append(
            {
                "title": title,
                "number": num,
                "congress": cgr,
                "type": bt,
                "latestAction": lact,
                "url": url,
            },
        )
    summary = "Congress.gov: no bills matched query."
    if bills:
        b0 = bills[0]
        summary = f"Congress.gov: {b0.get('title', '')[:120]} — {b0.get('type', '')} {b0.get('number', '')} ({b0.get('congress', '')})"
    return {
        "summary": summary,
        "bills": bills,
        "sourceUrl": path,
    }


def dispatch_adapter(adapter: str, params: dict[str, Any]) -> dict[str, Any]:
    if adapter == "fec":
        return fetch_fec_by_name(str(params.get("name") or ""))
    if adapter == "irs990":
        return fetch_irs990_by_name(str(params.get("name") or ""))
    if adapter == "lda":
        return fetch_lda_by_name(str(params.get("name") or ""))
    if adapter == "wikidata":
        return fetch_wikidata_by_name(str(params.get("name") or ""))
    if adapter == "congress":
        return fetch_congress_bills(str(params.get("query") or ""))
    raise ValueError(f"unknown adapter: {adapter}")
