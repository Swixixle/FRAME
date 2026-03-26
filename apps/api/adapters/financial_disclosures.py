"""House and Senate financial disclosure search, PDF range parsing, and wealth-delta estimates."""

from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

_LOG = logging.getLogger(__name__)

_FRAME_UA = "FRAME/1.0 (contact@frame.dev)"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# (regex, low_cents-ish as int dollars lower bound, upper bound) — House OGE columns use these brackets.
_ASSET_RANGE_SPECS: list[tuple[re.Pattern[str], int, int]] = [
    (re.compile(r"\$1,001\s*-\s*\$15,000", re.I), 1_001, 15_000),
    (re.compile(r"\$15,001\s*-\s*\$50,000", re.I), 15_001, 50_000),
    (re.compile(r"\$50,001\s*-\s*\$100,000", re.I), 50_001, 100_000),
    (re.compile(r"\$100,001\s*-\s*\$250,000", re.I), 100_001, 250_000),
    (re.compile(r"\$250,001\s*-\s*\$500,000", re.I), 250_001, 500_000),
    (re.compile(r"\$500,001\s*-\s*\$1,000,000", re.I), 500_001, 1_000_000),
    (re.compile(r"\$1,000,001\s*-\s*\$5,000,000", re.I), 1_000_001, 5_000_000),
    (re.compile(r"\$5,000,001\s*-\s*\$25,000,000", re.I), 5_000_001, 25_000_000),
    (re.compile(r"\$25,000,001\s*-\s*\$50,000,000", re.I), 25_000_001, 50_000_000),
]
_OVER_50M = re.compile(r"Over\s*\$50,000,000", re.I)

_HOUSE_MEMBER_SEARCH_POST = (
    "https://disclosures-clerk.house.gov/FinancialDisclosure/ViewMemberSearchResult"
)
_HOUSE_FD_BASE = "https://disclosures-clerk.house.gov/FinancialDisclosure/"
_FIN_YEAR_IN_PDF_PATH = re.compile(r"financial-pdfs/(\d{4})", re.I)

def _last_name(member_name: str) -> str:
    parts = (member_name or "").strip().split()
    if not parts:
        return ""
    return parts[-1].replace(",", "")


def _parse_house_financial_pdf_links(html: str, display_name: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if "financial-pdfs/" not in href.lower():
            continue
        m = _FIN_YEAR_IN_PDF_PATH.search(href)
        if not m:
            continue
        yr = int(m.group(1))
        if not (1990 <= yr <= 2035):
            continue
        doc_url = href if href.startswith("http") else urljoin(_HOUSE_FD_BASE, href)
        if doc_url in seen_urls:
            continue
        seen_urls.add(doc_url)
        out.append(
            {
                "filing_year": yr,
                "member_name": display_name,
                "document_url": doc_url,
                "chamber": "house",
            }
        )
    out.sort(key=lambda r: int(r.get("filing_year") or 0), reverse=True)
    return out


async def get_house_disclosures(member_name: str) -> list[dict[str, Any]]:
    try:
        ln = _last_name(member_name)
        if not ln:
            return []
        display = " ".join((member_name or "").split())
        form = {
            "LastName": ln,
            "FirstName": "",
            "FilingYear": "",
            "State": "",
            "District": "",
            "SearchType": "Annual",
        }
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers={
                "User-Agent": _FRAME_UA,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ) as client:
            r = await client.post(_HOUSE_MEMBER_SEARCH_POST, data=form)
            r.raise_for_status()
            rows = _parse_house_financial_pdf_links(r.text, display)
            if not rows:
                r2 = await client.post(
                    _HOUSE_MEMBER_SEARCH_POST,
                    data=form,
                    headers={
                        "User-Agent": _BROWSER_UA,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                r2.raise_for_status()
                rows = _parse_house_financial_pdf_links(r2.text, display)
        return rows
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("get_house_disclosures failed: %s", exc)
        return []


def senate_disclosure_stub_note(member_name: str) -> dict[str, Any]:
    """Advisory payload when `get_senate_disclosures` returns no rows (no public JSON/search API used)."""
    q = (member_name or "").strip() or "member"
    return {
        "error": "Senate financial disclosure search not available via public API",
        "manual_url": f"https://efts.senate.gov/LATEST/search-index?q={q}&type=annual",
        "source_type": "financial_disclosure",
    }


async def get_senate_disclosures(member_name: str) -> list[dict[str, Any]]:
    """Do not call senate.gov from this adapter — redirects/HTML only; use `senate_disclosure_stub_note`."""
    _ = (member_name or "").strip()
    return []


def _midpoints_from_asset_text(text: str) -> tuple[int, list[str]]:
    total_mid = 0
    found: list[str] = []
    for pat, lo, hi in _ASSET_RANGE_SPECS:
        for m in pat.finditer(text):
            mid = (lo + hi) / 2.0
            total_mid += mid
            found.append(m.group(0).strip())
    for m in _OVER_50M.finditer(text):
        lo = 50_000_000
        hi = 75_000_000
        total_mid += (lo + hi) / 2.0
        found.append(m.group(0).strip())
    return int(round(total_mid)), found


def _year_from_url(url: str) -> int | None:
    for m in re.finditer(r"(20\d{2})", url):
        y = int(m.group(1))
        if 1990 <= y <= 2035:
            return y
    return None


async def parse_house_disclosure_pdf(url: str, year: int | None = None) -> dict[str, Any]:
    try:
        u = (url or "").strip()
        if not u:
            return {}
        yr = year if year is not None else _year_from_url(u)
        if yr is None:
            yr = 0

        async with httpx.AsyncClient(
            timeout=120.0,
            follow_redirects=True,
            headers={"User-Agent": _FRAME_UA},
        ) as client:
            r = await client.get(u)
            r.raise_for_status()
            body = r.content
            ct = (r.headers.get("content-type") or "").lower()

            if "pdf" not in ct and not u.lower().split("?")[0].endswith(".pdf"):
                try:
                    html = body.decode("utf-8", errors="ignore")
                    soup = BeautifulSoup(html, "html.parser")
                    pdf_href = ""
                    for a in soup.find_all("a", href=True):
                        h = str(a.get("href") or "")
                        if ".pdf" in h.lower():
                            pdf_href = h
                            break
                    if pdf_href:
                        from urllib.parse import urljoin

                        if pdf_href.startswith("http"):
                            u2 = pdf_href
                        else:
                            u2 = urljoin(u, pdf_href)
                        r2 = await client.get(u2)
                        r2.raise_for_status()
                        body = r2.content
                        ct = (r2.headers.get("content-type") or "").lower()
                        u = u2
                except Exception:  # noqa: BLE001
                    pass

        if "pdf" not in ct and not u.lower().split("?")[0].endswith(".pdf"):
            return {
                "url": u,
                "year": yr,
                "estimated_assets": 0,
                "asset_ranges_found": [],
                "method": "skipped_not_pdf",
                "note": "Response was not a PDF; cannot parse asset ranges.",
            }

        def _read() -> str:
            reader = PdfReader(io.BytesIO(body))
            parts: list[str] = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n".join(parts)

        text = await asyncio.to_thread(_read)
        est, labels = _midpoints_from_asset_text(text)
        return {
            "url": u,
            "year": yr,
            "estimated_assets": est,
            "asset_ranges_found": labels[:200],
            "method": "pdf_midpoint_estimate",
            "note": "Asset values are self-reported ranges. Midpoint used for estimation. Not audited figures.",
        }
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("parse_house_disclosure_pdf failed for %s: %s", url, exc)
        return {
            "url": url,
            "year": year or 0,
            "estimated_assets": 0,
            "asset_ranges_found": [],
            "method": "error",
            "note": str(exc)[:300],
        }


def _pick_best_in_years(rows: list[dict[str, Any]], years: set[int]) -> dict[str, Any] | None:
    candidates = [r for r in rows if int(r.get("filing_year") or 0) in years]
    if not candidates:
        return None
    return max(candidates, key=lambda r: int(r.get("filing_year") or 0))


async def build_wealth_delta(member_name: str, chamber: str = "house") -> dict[str, Any]:
    ch = (chamber or "house").strip().lower()
    name = " ".join((member_name or "").split())
    pre_years = {2008, 2009}
    post_years = {2011, 2012, 2013, 2014}
    missing: str | None = None
    out: dict[str, Any] = {
        "member_name": name,
        "chamber": ch,
        "source_type": "financial_disclosure_delta",
    }

    try:
        rows = (
            await get_senate_disclosures(name)
            if ch == "senate"
            else await get_house_disclosures(name)
        )
        pre_rec = _pick_best_in_years(rows, pre_years)
        post_rec = _pick_best_in_years(rows, post_years)

        if not pre_rec:
            missing = "pre"
        if not post_rec:
            missing = "post" if not missing else "pre_and_post"

        async def _parse(rec: dict[str, Any] | None) -> dict[str, Any]:
            if not rec:
                return {}
            u = str(rec.get("document_url") or "").strip()
            fy = int(rec.get("filing_year") or 0)
            return await parse_house_disclosure_pdf(u, year=fy or None)

        pre_parse, post_parse = await asyncio.gather(_parse(pre_rec), _parse(post_rec))

        def _block(rec: dict[str, Any] | None, parsed: dict[str, Any]) -> dict[str, Any]:
            if not rec:
                return {
                    "year": 0,
                    "estimated_assets": 0,
                    "document_url": "",
                    "note": "Self-reported range, midpoint estimate — no filing in target years.",
                }
            return {
                "year": int(rec.get("filing_year") or parsed.get("year") or 0),
                "estimated_assets": int(parsed.get("estimated_assets") or 0),
                "document_url": str(rec.get("document_url") or ""),
                "note": "Self-reported range, midpoint estimate",
            }

        pre_b = _block(pre_rec, pre_parse)
        post_b = _block(post_rec, post_parse)
        out["pre_citizens_united"] = pre_b
        out["post_citizens_united"] = post_b

        pre_a = int(pre_b.get("estimated_assets") or 0)
        post_a = int(post_b.get("estimated_assets") or 0)
        if missing == "pre":
            out["missing"] = "pre"
        elif missing == "post":
            out["missing"] = "post"
        elif missing == "pre_and_post":
            out["missing"] = "pre_and_post"

        if pre_rec and post_rec and pre_b.get("document_url") and post_b.get("document_url"):
            delta = post_a - pre_a
            out["delta"] = delta
            out["delta_formatted"] = f"${delta:,.0f} estimated change"
        else:
            out["delta"] = None
            out["delta_formatted"] = "N/A — incomplete filing pair"

        out["disclaimer"] = (
            "Financial disclosure values are self-reported ranges required by federal law. "
            "Midpoint estimation is a mathematical approximation, not an audited figure. "
            "Source documents are linked for independent verification."
        )
        out["sources"] = [str(pre_b.get("document_url") or ""), str(post_b.get("document_url") or "")]
        return out
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("build_wealth_delta failed: %s", exc)
        out["error"] = str(exc)[:500]
        return out
