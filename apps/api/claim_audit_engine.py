"""
Claim / article audit spine for article_analysis receipts.

STUB: Full rubric (omission taxonomy, ledger, disposition scoring) is not implemented yet.
This module exists so main.py imports succeed; outputs are safe empty/minimal structures.
Replace incrementally without changing function names used by analyze-article.
"""

from __future__ import annotations

from typing import Any

# Bump when stub output shape or real rubric changes.
AUDIT_RUBRIC_VERSION = "0.0.0-stub"
CLAIM_EXTRACTION_VERSION = "extractor-v1-ref"
PARSER_EXTRACTION_VERSION = "article_ingest-v1-ref"


def build_claim_audits_for_results(claim_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One sparse audit row per claim; attach to claim_results by claim_id."""
    out: list[dict[str, Any]] = []
    for c in claim_results or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("claim_id")
        if cid is None:
            continue
        out.append(
            {
                "claim_id": cid,
                "audit_status": "stub_pending",
                "adapter_summary": {},
                "risk_signals": [],
                "note": "claim_audit_engine stub — scoring pending",
            },
        )
    return out


def build_article_omission_analysis(
    *,
    coverage_result: dict[str, Any],
    global_perspectives: dict[str, Any],
    what_nobody_is_covering: list[Any],
    claim_audits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Crosswalk comparative coverage vs claims — stub returns empty article block."""
    _ = (coverage_result, global_perspectives, what_nobody_is_covering, claim_audits)
    return {
        "article": {
            "omission_stub": True,
            "summary": "Cross-claim omission analysis not yet implemented.",
        },
        "claim_themes": [],
    }


def build_audit_unknowns(
    *,
    extraction_error: str | None,
    claim_results: list[dict[str, Any]],
    coverage_found: bool,
) -> list[str]:
    unknowns: list[str] = []
    if extraction_error:
        unknowns.append(f"Extraction limitation: {extraction_error}")
    if not claim_results:
        unknowns.append("No claims extracted for audit spine.")
    if not coverage_found:
        unknowns.append("Comparative coverage missing — omission cross-check limited.")
    return unknowns


def compute_article_disposition(
    *,
    claim_audits: list[dict[str, Any]],
    omission_article: dict[str, Any],
    coverage_insufficient: bool,
    claims_extracted: int,
    extraction_error: str | None,
) -> dict[str, Any]:
    _ = (claim_audits, omission_article)
    code = "insufficient_data"
    if extraction_error:
        code = "extraction_error"
    elif claims_extracted == 0:
        code = "no_claims"
    elif coverage_insufficient:
        code = "single_source_context"
    return {
        "disposition_code": code,
        "label": "Audit disposition pending full rubric.",
        "coverage_insufficient": coverage_insufficient,
        "claims_extracted": claims_extracted,
    }


def build_source_ledger(sources: list[dict[str, Any]], canonical_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cu = (canonical_url or "").strip()
    if cu:
        rows.append({"url": cu, "role": "primary_article", "ledger_note": "stub"})
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        u = str(s.get("url") or "").strip()
        if not u:
            continue
        rows.append(
            {
                "url": u,
                "role": str(s.get("source") or "expanded_source"),
                "title": s.get("title"),
                "ledger_note": "stub",
            },
        )
    return rows


def build_audit_summary_one_liner(
    *,
    claims_extracted: int,
    claim_audits: list[dict[str, Any]],
    omission_analysis: dict[str, Any],
    audit_unknowns: list[str],
) -> str:
    _ = (claim_audits, omission_analysis, audit_unknowns)
    return (
        f"{claims_extracted} claim(s) extracted; audit rubric {AUDIT_RUBRIC_VERSION} "
        "(full scoring pending)."
    )
