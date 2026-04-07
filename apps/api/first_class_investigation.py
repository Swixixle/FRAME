"""
First-class journalist and outlet investigations for PUBLIC EYE slim pipeline.
No GDELT, NewsAPI, Meta Ad Library, or proportionality — public-record adapters only.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from adapters import sec_edgar
from adapters_media import fetch_congress_bills, fetch_fec_by_name, fetch_irs990_by_name, fetch_lda_by_name
from enrichment.voting_record import get_recent_votes, search_member_by_name
from journalist_dossier_article import _fetch_fec_schedule_a_individual, _quoted_sources_payload

logger = logging.getLogger(__name__)

ANALYZE_ADAPTER_TIMEOUT = 8.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_source(
    data_sources: list[dict[str, Any]],
 *,
    adapter: str,
    ok: bool,
    source_error: bool = False,
    detail: str | None = None,
    rows_returned: int | None = None,
) -> None:
    row: dict[str, Any] = {
        "adapter": adapter,
        "ok": ok,
        "source_error": source_error,
    }
    if detail:
        row["detail"] = detail[:500]
    if rows_returned is not None:
        row["rows_returned"] = rows_returned
    data_sources.append(row)


async def _courtlistener_sync(name: str, *, limit: int = 5) -> list[dict[str, Any]] | None:
    q = (name or "").strip()
    if len(q) < 2:
        return []
    try:
        from adapters import courtlistener as cl

        return await asyncio.wait_for(
            cl.search_opinions(q[:200], limit=limit),
            timeout=ANALYZE_ADAPTER_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[investigation] CourtListener: %s", exc)
        return None


async def build_journalist_investigation_record(
    *,
    display_name: str,
    publication: str,
    article_url: str,
    article_topic: str | None,
    article_text: str | None,
    named_entities: list[Any] | None,
    linked_article_analysis_id: str,
) -> dict[str, Any]:
    """Assemble raw journalist investigation dict (unsigned). Uses 8s caps per adapter."""
    name = (display_name or "").strip()
    data_sources: list[dict[str, Any]] = []
    rid = str(uuid.uuid4())
    base: dict[str, Any] = {
        "report_id": rid,
        "receipt_type": "journalist_investigation",
        "generated_at": _now_iso(),
        "subject": {"display_name": name or None, "publication": (publication or "").strip() or None},
        "linked_article_analysis_id": linked_article_analysis_id,
        "linked_article_url": article_url,
        "data_sources": data_sources,
        "fec_donations": None,
        "courtlistener_opinions": None,
        "congress_member": None,
        "congress_votes": None,
        "congress_bills": None,
        "sec_edgar": None,
        "lda_filings": None,
        "quoted_sources": [],
    }

    if not name:
        base["quoted_sources"] = _quoted_sources_payload(article_text, named_entities, "")
        _append_source(
            data_sources,
            adapter="journalist_subject",
            ok=False,
            source_error=False,
            detail="no_byline",
        )
        return base

    def _fec_job() -> list[dict[str, Any]]:
        return _fetch_fec_schedule_a_individual(name, limit=8)

    try:
        fec_rows = await asyncio.wait_for(asyncio.to_thread(_fec_job), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["fec_donations"] = fec_rows or []
        _append_source(
            data_sources,
            adapter="fec_schedule_a",
            ok=True,
            rows_returned=len(fec_rows or []),
        )
    except asyncio.TimeoutError:
        base["fec_donations"] = None
        _append_source(
            data_sources,
            adapter="fec_schedule_a",
            ok=False,
            source_error=True,
            detail=f"timeout_after_{ANALYZE_ADAPTER_TIMEOUT}s",
        )
    except Exception as exc:  # noqa: BLE001
        base["fec_donations"] = None
        _append_source(
            data_sources,
            adapter="fec_schedule_a",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    # CourtListener
    cl_rows = await _courtlistener_sync(name)
    if cl_rows is None:
        base["courtlistener_opinions"] = None
        _append_source(
            data_sources,
            adapter="courtlistener",
            ok=False,
            source_error=True,
            detail="error_or_timeout",
        )
    else:
        slim = []
        for r in cl_rows[:5]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "case_name": r.get("case_name"),
                    "court": r.get("court"),
                    "date_filed": r.get("date_filed"),
                    "url": r.get("url") or r.get("source_url"),
                },
            )
        base["courtlistener_opinions"] = slim
        _append_source(
            data_sources,
            adapter="courtlistener",
            ok=True,
            rows_returned=len(slim),
        )

    # ProPublica Congress member + votes (existing module; uses optional PROPUBLICA_API_KEY)
    def _pp_member() -> dict[str, Any] | None:
        return search_member_by_name(name)

    try:
        mem = await asyncio.wait_for(asyncio.to_thread(_pp_member), timeout=ANALYZE_ADAPTER_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        mem = {"error": str(exc)[:200]}
    if isinstance(mem, dict) and mem.get("error"):
        base["congress_member"] = None
        _append_source(
            data_sources,
            adapter="propublica_congress_member",
            ok=False,
            source_error=True,
            detail=str(mem.get("error")),
        )
    elif isinstance(mem, dict) and mem.get("member_id"):
        base["congress_member"] = mem
        _append_source(data_sources, adapter="propublica_congress_member", ok=True)
        mid = str(mem.get("member_id") or "")

        def _votes() -> list[dict[str, Any]]:
            return get_recent_votes(mid, limit=10)

        try:
            votes = await asyncio.wait_for(asyncio.to_thread(_votes), timeout=ANALYZE_ADAPTER_TIMEOUT)
            base["congress_votes"] = votes
            _append_source(
                data_sources,
                adapter="propublica_congress_votes",
                ok=True,
                rows_returned=len(votes),
            )
        except Exception as exc:  # noqa: BLE001
            base["congress_votes"] = None
            _append_source(
                data_sources,
                adapter="propublica_congress_votes",
                ok=False,
                source_error=True,
                detail=str(exc)[:300],
            )
    else:
        base["congress_member"] = None
        _append_source(
            data_sources,
            adapter="propublica_congress_member",
            ok=True,
            detail="no_member_match",
            rows_returned=0,
        )

    # Congress.gov bills (CONGRESS_API_KEY)
    def _cg_bills() -> dict[str, Any]:
        return fetch_congress_bills(name[:200])

    try:
        bills_wrap = await asyncio.wait_for(asyncio.to_thread(_cg_bills), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["congress_bills"] = bills_wrap
        err = bills_wrap.get("error") if isinstance(bills_wrap, dict) else None
        if err == "missing_api_key":
            _append_source(
                data_sources,
                adapter="congress_gov",
                ok=False,
                source_error=False,
                detail="missing_CONGRESS_API_KEY",
            )
        elif isinstance(bills_wrap, dict) and bills_wrap.get("bills"):
            _append_source(
                data_sources,
                adapter="congress_gov",
                ok=True,
                rows_returned=len(bills_wrap.get("bills") or []),
            )
        else:
            _append_source(
                data_sources,
                adapter="congress_gov",
                ok=True,
                detail="no_bills",
                rows_returned=0,
            )
    except Exception as exc:  # noqa: BLE001
        base["congress_bills"] = None
        _append_source(
            data_sources,
            adapter="congress_gov",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    # SEC EDGAR entity search (needs SEC_EDGAR_USER_AGENT for reliability)
    def _sec() -> dict[str, Any]:
        return sec_edgar.search_entity(name[:120])

    try:
        sec_r = await asyncio.wait_for(asyncio.to_thread(_sec), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["sec_edgar"] = sec_r
        nent = len((sec_r or {}).get("entities") or []) if isinstance(sec_r, dict) else 0
        _append_source(
            data_sources,
            adapter="sec_edgar",
            ok=True,
            rows_returned=nent,
            detail=None if nent else "no_entity_hits",
        )
    except Exception as exc:  # noqa: BLE001
        base["sec_edgar"] = None
        _append_source(
            data_sources,
            adapter="sec_edgar",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    # Senate LDA
    def _lda() -> dict[str, Any]:
        return fetch_lda_by_name(name)

    try:
        lda_r = await asyncio.wait_for(asyncio.to_thread(_lda), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["lda_filings"] = lda_r
        fc = int(lda_r.get("filingCount") or len(lda_r.get("filings") or [])) if isinstance(lda_r, dict) else 0
        _append_source(data_sources, adapter="lda", ok=True, rows_returned=fc)
    except Exception as exc:  # noqa: BLE001
        base["lda_filings"] = None
        _append_source(
            data_sources,
            adapter="lda",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    base["quoted_sources"] = _quoted_sources_payload(article_text, named_entities, name)
    return base


async def build_outlet_investigation_record(
    *,
    outlet_display: str,
    domain: str,
    linked_article_analysis_id: str,
    article_url: str,
) -> dict[str, Any]:
    """Assemble raw outlet investigation dict (unsigned)."""
    from publisher_registry import lookup_domain, parent_company_for_domain

    data_sources: list[dict[str, Any]] = []
    rid = str(uuid.uuid4())
    dom = (domain or "").strip().lower().replace("www.", "")
    pub = lookup_domain(dom) if dom else {}
    outlet_name = str(
        pub.get("name") or outlet_display or dom or "unknown",
    ).strip()
    parent = parent_company_for_domain(dom) if dom else None

    base: dict[str, Any] = {
        "report_id": rid,
        "receipt_type": "outlet_investigation",
        "generated_at": _now_iso(),
        "subject": {
            "outlet": outlet_name,
            "domain": dom or None,
            "parent_company": parent,
            "registry_match": bool(pub),
        },
        "linked_article_analysis_id": linked_article_analysis_id,
        "linked_article_url": article_url,
        "data_sources": data_sources,
        "courtlistener_opinions": None,
        "sec_edgar": None,
        "fec_snapshot": None,
        "lda_filings": None,
        "irs990": None,
    }

    # CourtListener on org name
    cl_rows = await _courtlistener_sync(outlet_name[:200])
    if cl_rows is None:
        base["courtlistener_opinions"] = None
        _append_source(
            data_sources,
            adapter="courtlistener",
            ok=False,
            source_error=True,
            detail="error_or_timeout",
        )
    else:
        slim = []
        for r in cl_rows[:5]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "case_name": r.get("case_name"),
                    "court": r.get("court"),
                    "date_filed": r.get("date_filed"),
                    "url": r.get("url") or r.get("source_url"),
                },
            )
        base["courtlistener_opinions"] = slim
        _append_source(
            data_sources,
            adapter="courtlistener",
            ok=True,
            rows_returned=len(slim),
        )

    # SEC
    def _sec() -> dict[str, Any]:
        q = (parent or outlet_name)[:120]
        return sec_edgar.search_entity(q)

    try:
        sec_r = await asyncio.wait_for(asyncio.to_thread(_sec), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["sec_edgar"] = sec_r
        nent = len((sec_r or {}).get("entities") or []) if isinstance(sec_r, dict) else 0
        _append_source(
            data_sources,
            adapter="sec_edgar",
            ok=True,
            rows_returned=nent,
            detail=None if nent else "no_entity_hits",
        )
    except Exception as exc:  # noqa: BLE001
        base["sec_edgar"] = None
        _append_source(
            data_sources,
            adapter="sec_edgar",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    # FEC candidate search (name match for org / PAC labels — best-effort)
    def _fec() -> dict[str, Any]:
        return fetch_fec_by_name(outlet_name[:100])

    try:
        fec_r = await asyncio.wait_for(asyncio.to_thread(_fec), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["fec_snapshot"] = fec_r
        _append_source(data_sources, adapter="fec", ok=True)
    except Exception as exc:  # noqa: BLE001
        base["fec_snapshot"] = None
        _append_source(
            data_sources,
            adapter="fec",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    def _lda() -> dict[str, Any]:
        return fetch_lda_by_name(outlet_name)

    try:
        lda_r = await asyncio.wait_for(asyncio.to_thread(_lda), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["lda_filings"] = lda_r
        _append_source(data_sources, adapter="lda", ok=True)
    except Exception as exc:  # noqa: BLE001
        base["lda_filings"] = None
        _append_source(
            data_sources,
            adapter="lda",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    def _990() -> dict[str, Any]:
        return fetch_irs990_by_name(outlet_name)

    try:
        irs = await asyncio.wait_for(asyncio.to_thread(_990), timeout=ANALYZE_ADAPTER_TIMEOUT)
        base["irs990"] = irs
        _append_source(data_sources, adapter="irs990", ok=True)
    except Exception as exc:  # noqa: BLE001
        base["irs990"] = None
        _append_source(
            data_sources,
            adapter="irs990",
            ok=False,
            source_error=True,
            detail=str(exc)[:300],
        )

    return base
