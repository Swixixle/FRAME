"""House and Senate public financial disclosure search (HTML / JSON index)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

_LOG = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Frame/1.0 (+https://getframe.dev)"
)


def _last_name(member_name: str) -> str:
    parts = (member_name or "").strip().split()
    if not parts:
        return ""
    return parts[-1].replace(",", "")


async def get_house_disclosures(member_name: str) -> list[dict[str, Any]]:
    try:
        ln = _last_name(member_name)
        if not ln:
            return []
        post_url = "https://disclosures.house.gov/FinancialDisclosure/ViewMemberSearchResult"
        out: list[dict[str, Any]] = []
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            r = await client.post(
                post_url,
                data={
                    "LastName": ln,
                    "State": "",
                    "District": "",
                    "FilingYear": "",
                    "SearchType": "Annual",
                },
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        fn = " ".join((member_name or "").split())
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 1:
                continue
            row_text = " ".join(c.get_text(" ", strip=True) for c in cells)
            link = tr.find("a", href=True)
            doc_url = ""
            if link:
                href = str(link["href"]).strip()
                if href.startswith("http"):
                    doc_url = href
                else:
                    doc_url = f"https://disclosures.house.gov{href}" if href.startswith("/") else f"https://disclosures.house.gov/{href.lstrip('/')}"
            filing_year = 0
            m_year = re.search(r"(20\d{2})", row_text)
            if m_year:
                filing_year = int(m_year.group(1))
            if not doc_url and ln.lower() not in row_text.lower():
                continue
            out.append(
                {
                    "filing_year": filing_year,
                    "document_url": doc_url,
                    "member_name": fn,
                }
            )
            if len(out) >= 10:
                break
        return out[:10]
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("get_house_disclosures failed: %s", exc)
        return []


async def get_senate_disclosures(member_name: str) -> list[dict[str, Any]]:
    try:
        q = (member_name or "").strip()
        if not q:
            return []
        url = "https://efts.senate.gov/LATEST/search-index"
        params = {"q": f'"{q}"', "type": "annual"}
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                data = r.json()
            else:
                try:
                    data = r.json()
                except Exception:  # noqa: BLE001
                    _LOG.warning("get_senate_disclosures: non-JSON response")
                    return []
        out: list[dict[str, Any]] = []
        hits: list[Any] = []
        if isinstance(data, dict):
            hits = (
                data.get("results")
                or data.get("hits")
                or data.get("documents")
                or data.get("filings")
                or data.get("data")
                or []
            )
        elif isinstance(data, list):
            hits = data
        if not isinstance(hits, list):
            return []
        for h in hits[:10]:
            if not isinstance(h, dict):
                continue
            doc_url = str(
                h.get("document_url")
                or h.get("url")
                or h.get("uri")
                or h.get("downloadUrl")
                or h.get("href")
                or ""
            ).strip()
            if doc_url and not doc_url.startswith("http"):
                doc_url = (
                    f"https://efts.senate.gov{doc_url}"
                    if doc_url.startswith("/")
                    else f"https://efts.senate.gov/{doc_url.lstrip('/')}"
                )
            fd = str(h.get("filing_date") or h.get("filed") or h.get("date") or "").strip()
            filer = str(h.get("filer_name") or h.get("name") or h.get("filerName") or q).strip()
            out.append(
                {
                    "filing_date": fd,
                    "document_url": doc_url,
                    "filer_name": filer,
                }
            )
        return out[:10]
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("get_senate_disclosures failed: %s", exc)
        return []
