"""
Accumulate journalist/outlet dossier findings into entity_profiles + entity_evidence_log.

Sync functions suitable for asyncio.to_thread. No-ops when DATABASE_URL unset.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import psycopg2
import psycopg2.extras

from adapters.fact_checkers import fetch_politifact_aggregate

logger = logging.getLogger(__name__)


def entity_slugify(label: str) -> str:
    s = (label or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:120]
    return s or ""


def compute_journalist_entity_slug(journalist_dossier: dict[str, Any] | None) -> str | None:
    if not isinstance(journalist_dossier, dict):
        return None
    name = str(journalist_dossier.get("display_name") or "").strip()
    slug = entity_slugify(name)
    return slug or None


def compute_outlet_entity_slug(
    outlet_dossier: dict[str, Any] | None,
    article: dict[str, Any] | None,
) -> str | None:
    if isinstance(outlet_dossier, dict):
        d = str(outlet_dossier.get("domain") or "").strip().lower().replace("www.", "")
        if d:
            return entity_slugify(d) or d[:120]
        o = str(outlet_dossier.get("outlet") or "").strip()
        if o:
            s = entity_slugify(o)
            return s or None
    if isinstance(article, dict):
        from urllib.parse import urlparse

        u = str(article.get("canonical_url") or article.get("url") or "").strip()
        try:
            host = (urlparse(u).netloc or "").lower().replace("www.", "")
            if host:
                return entity_slugify(host) or host[:120]
        except Exception:  # noqa: BLE001
            pass
    return None


def _conn():
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        return None
    return psycopg2.connect(url)


def _append_evidence(
    cur: Any,
    *,
    slug: str,
    evidence_type: str,
    payload: dict[str, Any],
    article_url: str,
    receipt_id: str | None,
) -> None:
    cur.execute(
        """
        INSERT INTO entity_evidence_log
            (entity_slug, evidence_type, evidence_json, article_url, receipt_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            slug,
            evidence_type,
            psycopg2.extras.Json(payload),
            article_url,
            receipt_id,
        ),
    )


def persist_article_entities_sync(receipt: dict[str, Any], article_url: str) -> None:
    rid = str(receipt.get("report_id") or receipt.get("receipt_id") or "").strip() or None
    conn = _conn()
    if not conn:
        return

    coverage_core_entities: list[str] = []
    _cce = receipt.get("coverage_core_entities")
    if isinstance(_cce, list):
        coverage_core_entities = [str(x).strip() for x in _cce if x and str(x).strip()]

    jd = receipt.get("journalist_dossier") if isinstance(receipt.get("journalist_dossier"), dict) else None
    od = receipt.get("outlet_dossier") if isinstance(receipt.get("outlet_dossier"), dict) else None
    art = receipt.get("article") if isinstance(receipt.get("article"), dict) else {}

    try:
        with conn.cursor() as cur:
            if jd:
                slug = compute_journalist_entity_slug(jd)
                name = str(jd.get("display_name") or "").strip()
                if slug and name:
                    cur.execute(
                        "SELECT is_static FROM entity_profiles WHERE entity_slug = %s",
                        (slug,),
                    )
                    row = cur.fetchone()
                    is_static = bool(row and row[0])
                    aff = str(jd.get("outlet") or "").strip() or None
                    funding = {"fec_donations": jd.get("fec_donations") or []}
                    pf = fetch_politifact_aggregate(name, limit=15)
                    factcheck = pf if pf else None

                    if is_static:
                        _append_evidence(
                            cur,
                            slug=slug,
                            evidence_type="beat_coverage",
                            payload={
                                "journalist_dossier_snapshot": jd,
                                "note": "profile is_static — row not overwritten",
                                "coverage_core_entities": coverage_core_entities,
                            },
                            article_url=article_url,
                            receipt_id=rid,
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO entity_profiles (
                                entity_slug, entity_name, entity_type, current_affiliation,
                                funding_json, factcheck_json, overall_integrity,
                                first_seen, last_updated, evidence_count
                            )
                            VALUES (%s, %s, 'journalist', %s, %s, %s, 'insufficient_data',
                                    NOW(), NOW(), 1)
                            ON CONFLICT (entity_slug) DO UPDATE SET
                                entity_name = EXCLUDED.entity_name,
                                current_affiliation = COALESCE(EXCLUDED.current_affiliation,
                                    entity_profiles.current_affiliation),
                                funding_json = EXCLUDED.funding_json,
                                factcheck_json = COALESCE(
                                    EXCLUDED.factcheck_json,
                                    entity_profiles.factcheck_json
                                ),
                                last_updated = NOW(),
                                evidence_count = entity_profiles.evidence_count + 1
                            """,
                            (
                                slug,
                                name,
                                aff,
                                psycopg2.extras.Json(funding),
                                psycopg2.extras.Json(factcheck) if factcheck else None,
                            ),
                        )

                        _append_evidence(
                            cur,
                            slug=slug,
                            evidence_type="beat_coverage",
                            payload={
                                "beat_history": jd.get("beat_history"),
                                "story_count_on_topic": jd.get("story_count_on_topic"),
                                "coverage_gap": jd.get("coverage_gap"),
                                # From extract_query_terms / coverage bundle — do not re-derive.
                                "coverage_core_entities": coverage_core_entities,
                            },
                            article_url=article_url,
                            receipt_id=rid,
                        )
                        for d in jd.get("fec_donations") or []:
                            if isinstance(d, dict):
                                _append_evidence(
                                    cur,
                                    slug=slug,
                                    evidence_type="fec_donation",
                                    payload=d,
                                    article_url=article_url,
                                    receipt_id=rid,
                                )
                        for q in jd.get("quoted_sources") or []:
                            if isinstance(q, dict):
                                _append_evidence(
                                    cur,
                                    slug=slug,
                                    evidence_type="quote",
                                    payload=q,
                                    article_url=article_url,
                                    receipt_id=rid,
                                )

            if od:
                slug = compute_outlet_entity_slug(od, art)
                oname = str(od.get("outlet") or slug or "outlet").strip()
                if slug and oname:
                    cur.execute(
                        "SELECT is_static FROM entity_profiles WHERE entity_slug = %s",
                        (slug,),
                    )
                    row = cur.fetchone()
                    is_static = bool(row and row[0])
                    outlet_payload = {
                        "parent_company": od.get("parent_company"),
                        "advertiser_conflict_flag": od.get("advertiser_conflict_flag"),
                        "advertiser_conflict_note": od.get("advertiser_conflict_note"),
                        "top_advertisers": od.get("top_advertisers"),
                        "coverage_core_entities": coverage_core_entities,
                    }
                    if not is_static:
                        cur.execute(
                            """
                            INSERT INTO entity_profiles (
                                entity_slug, entity_name, entity_type, current_affiliation,
                                funding_json, overall_integrity,
                                first_seen, last_updated, evidence_count
                            )
                            VALUES (%s, %s, 'outlet', NULL, %s, 'insufficient_data',
                                    NOW(), NOW(), 1)
                            ON CONFLICT (entity_slug) DO UPDATE SET
                                entity_name = EXCLUDED.entity_name,
                                funding_json = EXCLUDED.funding_json,
                                last_updated = NOW(),
                                evidence_count = entity_profiles.evidence_count + 1
                            """,
                            (
                                slug,
                                oname,
                                psycopg2.extras.Json(outlet_payload),
                            ),
                        )
                    _append_evidence(
                        cur,
                        slug=slug,
                        evidence_type="advertiser_relationship",
                        payload=outlet_payload,
                        article_url=article_url,
                        receipt_id=rid,
                    )

        conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[entity_persistence] %s", exc)
        conn.rollback()
    finally:
        conn.close()
