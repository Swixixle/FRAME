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

# Schedule A: dollar range (spaces around hyphen optional). "Over" open-ended.
_SCHEDULE_A_RANGE_RE = re.compile(r"\$[\d,]+\s*-\s*\$[\d,]+")
_SCHEDULE_A_OVER_RE = re.compile(r"Over\s*\$[\d,]+", re.I)
_SCHEDULE_A_HEADER_RE = re.compile(r"schedule\s*[^a-z0-9]{0,15}a", re.I)
_SCHEDULE_BC_RE = re.compile(r"schedule\s*[bc](?:\s|\.|:|,|\(|$|<)", re.I)
# Schedule A rows: asset range, then income type(s), then income range — skip the latter.
_INCOME_TYPE_BEFORE_RANGE = re.compile(
    r"(capital\s+gains|dividends?|interest|rent(?:al)?|royalt(?:y|ies))\s*,?\s*$",
    re.I,
)

_HOUSE_MEMBER_SEARCH_POST = (
    "https://disclosures-clerk.house.gov/FinancialDisclosure/ViewMemberSearchResult"
)
# PDFs live under /public_disc/... — /FinancialDisclosure/public_disc/... returns 404 on clerk host.
_HOUSE_FD_BASE = "https://disclosures-clerk.house.gov/"
_FIN_YEAR_IN_PDF_PATH = re.compile(r"financial-pdfs/(\d{4})", re.I)
_BROKEN_CLERK_PDF_PREFIX = "https://disclosures-clerk.house.gov/FinancialDisclosure/public_disc/"
_FIXED_CLERK_PDF_PREFIX = "https://disclosures-clerk.house.gov/public_disc/"


def _normalize_house_clerk_pdf_url(url: str) -> str:
    u = (url or "").strip()
    if _BROKEN_CLERK_PDF_PREFIX in u:
        u = u.replace(_BROKEN_CLERK_PDF_PREFIX, _FIXED_CLERK_PDF_PREFIX)
    return u


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
        if href.startswith("http"):
            doc_url = _normalize_house_clerk_pdf_url(href)
        else:
            doc_url = _normalize_house_clerk_pdf_url(urljoin(_HOUSE_FD_BASE, href))
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


def _parse_money_amount(tok: str) -> int:
    s = tok.strip().lstrip("$").replace(",", "")
    return int(s)


def _schedule_a_window(full_text: str) -> str:
    """Slice text from Schedule A (with Asset nearby) through next Schedule B/C or EOF."""
    if not (full_text or "").strip():
        return ""
    text = full_text
    for m in _SCHEDULE_A_HEADER_RE.finditer(text):
        span_end = min(len(text), m.end() + 400)
        chunk = text[m.start() : span_end]
        if not re.search(r"asset", chunk, re.I):
            continue
        start_i = m.start()
        after = text[m.end() :]
        end_m = _SCHEDULE_BC_RE.search(after)
        if end_m:
            return text[start_i : m.end() + end_m.start()]
        return text[start_i:]
    return ""


def _likely_schedule_a_income_column_range(window: str, m: re.Match[str]) -> bool:
    before = window[max(0, m.start() - 72) : m.start()]
    return bool(_INCOME_TYPE_BEFORE_RANGE.search(before))


def _midpoints_from_schedule_a_window(window: str) -> tuple[int, list[str]]:
    total_mid = 0.0
    found: list[str] = []
    for m in _SCHEDULE_A_RANGE_RE.finditer(window):
        raw = m.group(0)
        if _likely_schedule_a_income_column_range(window, m):
            continue
        compact = re.sub(r"\s*-\s*", "-", raw.strip())
        parts = compact.split("-", 1)
        if len(parts) != 2:
            continue
        try:
            lo = _parse_money_amount(parts[0])
            hi = _parse_money_amount(parts[1])
        except ValueError:
            continue
        if lo > hi:
            lo, hi = hi, lo
        total_mid += (lo + hi) / 2.0
        found.append(raw.strip())
    for m in _SCHEDULE_A_OVER_RE.finditer(window):
        raw = m.group(0).strip()
        found.append(raw)
        inner = re.search(r"\$([\d,]+)", raw, re.I)
        if not inner:
            continue
        lo = int(inner.group(1).replace(",", ""))
        if lo >= 50_000_000:
            total_mid += (50_000_000 + 75_000_000) / 2.0
        else:
            total_mid += lo * 1.25
    return int(round(total_mid)), found


def _year_from_url(url: str) -> int | None:
    for m in re.finditer(r"(20\d{2})", url):
        y = int(m.group(1))
        if 1990 <= y <= 2035:
            return y
    return None


async def parse_house_disclosure_pdf(url: str, year: int | None = None) -> dict[str, Any]:
    try:
        u = _normalize_house_clerk_pdf_url((url or "").strip())
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

        def _read() -> tuple[str, str, list[str]]:
            reader = PdfReader(io.BytesIO(body))
            parts: list[str] = []
            page0_text = ""
            for i, page in enumerate(reader.pages):
                raw = page.extract_text() or ""
                if i == 0:
                    page0_text = raw
                parts.append(raw)
            joined = " ".join(parts)
            return joined, page0_text, parts

        text, page1_extracted, per_page = await asyncio.to_thread(_read)
        _LOG.debug(
            "parse_house_disclosure_pdf page1 first 500 chars (url=%s): %r",
            u,
            (page1_extracted or "")[:500],
        )
        if per_page and not any((p or "").strip() for p in per_page):
            return {
                "url": u,
                "year": yr,
                "estimated_assets": None,
                "method": "scanned_pdf_no_text_layer",
                "note": (
                    "This filing is a scanned image PDF. Text extraction not possible without OCR. "
                    "See document_url for manual review."
                ),
                "document_url": u,
            }

        window = _schedule_a_window(text)
        est, labels = _midpoints_from_schedule_a_window(window)
        return {
            "url": u,
            "year": yr,
            "estimated_assets": est,
            "asset_ranges_found": labels[:200],
            "method": "pdf_midpoint_schedule_a",
            "note": "Schedule A asset column only; midpoints from self-reported ranges. Not audited figures.",
            "document_url": u,
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
            doc_u = _normalize_house_clerk_pdf_url(str(rec.get("document_url") or ""))
            est_raw = parsed.get("estimated_assets")
            if est_raw is None:
                return {
                    "year": int(rec.get("filing_year") or parsed.get("year") or 0),
                    "estimated_assets": None,
                    "document_url": doc_u,
                    "note": str(
                        parsed.get("note")
                        or "Scanned PDF; no text layer. See document for manual review."
                    ),
                }
            return {
                "year": int(rec.get("filing_year") or parsed.get("year") or 0),
                "estimated_assets": int(est_raw),
                "document_url": doc_u,
                "note": str(parsed.get("note") or "Schedule A midpoint estimate from self-reported ranges."),
            }

        pre_b = _block(pre_rec, pre_parse)
        post_b = _block(post_rec, post_parse)
        out["pre_citizens_united"] = pre_b
        out["post_citizens_united"] = post_b

        pre_a = pre_b.get("estimated_assets")
        post_a = post_b.get("estimated_assets")
        if missing == "pre":
            out["missing"] = "pre"
        elif missing == "post":
            out["missing"] = "post"
        elif missing == "pre_and_post":
            out["missing"] = "pre_and_post"

        if pre_rec and post_rec and pre_b.get("document_url") and post_b.get("document_url"):
            if pre_a is None or post_a is None:
                out["delta"] = None
                out["delta_formatted"] = (
                    "N/A — one or both filings are scanned image PDFs. See source documents."
                )
            else:
                delta = int(post_a) - int(pre_a)
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
