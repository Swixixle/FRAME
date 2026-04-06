"""
Outlet dossier enrichment for article_analysis: registry + Wikipedia summary + Meta Ad Library.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from adapters.meta_ad_library import query_ad_library
from llm_client import LLMMessage, llm_complete
from publisher_registry import lookup_domain, parent_company_for_domain
from services.proportionality_client import (
    fetch_proportionality_packet,
    proportionality_fetch_params_dict,
)

logger = logging.getLogger(__name__)


def _topic_tokens(topic: str | None) -> set[str]:
    if not topic:
        return set()
    return {t.lower() for t in re.findall(r"[A-Za-z]{4,}", topic) if len(t) >= 4}


def _wikipedia_summary_extract(title_candidate: str) -> tuple[str | None, str | None]:
    """Returns (plain extract text, page title if found)."""
    slug = (title_candidate or "").strip().replace(" ", "_")
    if len(slug) < 2:
        return None, None
    try:
        path = quote(slug, safe="()%")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{path}"
        r = httpx.get(
            url,
            timeout=12.0,
            headers={"User-Agent": "PUBLIC_EYE_Frame/1.0 (research; +https://frame-2yxu.onrender.com)"},
            follow_redirects=True,
        )
        if r.status_code != 200:
            return None, None
        data = r.json()
        extract = str(data.get("extract") or "").strip()
        title = str(data.get("title") or "").strip()
        return (extract or None), (title or None)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[outlet_dossier_article] wikipedia: %s", exc)
        return None, None


def _claude_parent_from_summary(summary: str, outlet_name: str) -> dict[str, Any]:
    try:
        resp = llm_complete(
            system='You extract ownership facts only. Respond with JSON only: {"parent_company": string|null, "ownership_note": string|null}.',
            messages=[
                LLMMessage(
                    role="user",
                    content=(
                        f'Media outlet: "{outlet_name}"\n\nWikipedia summary:\n{summary[:4500]}\n\n'
                        "From this summary, extract the parent company or owner of this media outlet. "
                        "If not determinable, use nulls for both fields."
                    ),
                )
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = (resp.text or "").strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
                if raw.lstrip().startswith("json"):
                    raw = raw.lstrip()[4:].lstrip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"parent_company": None, "ownership_note": None}
        return {
            "parent_company": data.get("parent_company"),
            "ownership_note": data.get("ownership_note"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("[outlet_dossier_article] claude parent: %s", exc)
        return {"parent_company": None, "ownership_note": None}


def _aggregate_advertisers(meta: dict[str, Any]) -> list[dict[str, Any]]:
    if meta.get("status") != "results_found":
        return []
    ads = meta.get("ads") or []
    by_funding: dict[str, dict[str, Any]] = {}
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fe = str(ad.get("funding_entity") or "").strip() or "unknown"
        row = by_funding.setdefault(
            fe,
            {"funding_entity": fe, "spend_upper_sum": 0, "ad_count": 0, "spend_display_sample": ""},
        )
        row["ad_count"] += 1
        u = ad.get("spend_upper_bound")
        if isinstance(u, int):
            row["spend_upper_sum"] += u
        if not row.get("spend_display_sample") and ad.get("spend_display"):
            row["spend_display_sample"] = str(ad.get("spend_display"))
    ranked = sorted(
        by_funding.values(),
        key=lambda x: (x.get("spend_upper_sum") or 0, x.get("ad_count") or 0),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for r in ranked[:5]:
        out.append(
            {
                "name": r.get("funding_entity"),
                "political_issue_ads_count": r.get("ad_count"),
                "spend_upper_bound_sum_est": r.get("spend_upper_sum"),
                "spend_note": r.get("spend_display_sample") or "Meta range; political/issue ads only",
            }
        )
    return out


def _topic_cluster_phrase(article_topic: str | None, matched_tokens: set[str]) -> str:
    t = (article_topic or "").strip()
    if t:
        if len(t) <= 140:
            return t.rstrip(".")
        cut = t[:137].rsplit(" ", 1)[0]
        return f"{cut}…"
    if matched_tokens:
        return " ".join(sorted(matched_tokens))[:120].strip() or "article topic tokens"
    return "article topic"


def _spend_phrase_for_receipt(adv: dict[str, Any]) -> str:
    upper = adv.get("spend_upper_bound_sum_est")
    if isinstance(upper, (int, float)) and upper > 0:
        if upper >= 1_000_000:
            v = upper / 1_000_000
            s = f"${v:.1f}M".replace(".0M", "M")
        elif upper >= 1_000:
            v = upper / 1_000
            s = f"${v:.1f}K".replace(".0K", "K")
        else:
            s = f"${int(upper):,}"
        return f"{s} upper-bound (Meta political/issue ads for this query; not verified as display spend)"
    sn = str(adv.get("spend_note") or "").strip()
    if sn:
        return sn[:120]
    ac = adv.get("political_issue_ads_count")
    if isinstance(ac, int) and ac > 0:
        return f"{ac} political/issue ad(s) in snapshot; spend not summed"
    return "spend not disclosed in Ad Library snapshot"


def _advertiser_stake_conflict(
    article_topic: str | None,
    advertisers: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    tokens = _topic_tokens(article_topic)
    if not tokens:
        return False, None

    hits: list[tuple[dict[str, Any], set[str]]] = []
    for adv in advertisers:
        blob = (str(adv.get("name") or "") + " " + str(adv.get("spend_note") or "")).lower()
        matched = {tok for tok in tokens if tok in blob}
        if matched:
            hits.append((adv, matched))

    if not hits:
        return False, None

    all_matched = set()
    for _adv, m in hits:
        all_matched |= m
    cluster = _topic_cluster_phrase(article_topic, all_matched)

    segments: list[str] = []
    for adv, matched in hits[:5]:
        name = str(adv.get("name") or "unknown").strip()
        spend_p = _spend_phrase_for_receipt(adv)
        overlap = ", ".join(sorted(matched))
        segments.append(f"{name} ({spend_p}) matches topic tokens: {overlap}")

    note = (
        f"{'; '.join(segments)}. Topic cluster: {cluster}. "
        "Source: Meta Ad Library (political/issue ads); string overlap only — not proof of editorial influence."
    )
    return True, note


async def _courtlistener_opinion_hits(name: str, *, limit: int = 2) -> list[dict[str, Any]]:
    q = (name or "").strip()
    if len(q) < 2:
        return []
    try:
        from adapters import courtlistener as cl

        return await asyncio.wait_for(cl.search_opinions(q[:200], limit=limit), timeout=18.0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[outlet_dossier_article] CourtListener: %s", exc)
        return []


async def _collect_outlet_proportionality_records(
    outlet_name: str,
    parent_company: str | None,
    top_advertisers: list[dict[str, Any]],
    meta_status: str | None,
    advertiser_conflict_flag: bool,
) -> list[dict[str, Any]]:
    """
    Triggers only from documented legal index hits (CourtListener) or political ad + CL hit
    on the advertiser — not framing scores.
    """
    records: list[dict[str, Any]] = []
    parent = (parent_company or "").strip()
    outlet = (outlet_name or "").strip()

    if parent:
        rows = await _courtlistener_opinion_hits(parent, limit=2)
        if rows:
            top = rows[0]
            case = str(top.get("case_name") or "").strip() or parent
            vt = case[:200]
            params = proportionality_fetch_params_dict(
                category="legal",
                violation_type=vt,
                charge_status="public court opinion / docket index",
                amount_involved=None,
            )
            pkt = await fetch_proportionality_packet(
                category=params["category"],
                violation_type=params["violation_type"],
                charge_status=params["charge_status"],
                amount_involved=params["amount_involved"],
            )
            records.append(
                {
                    "trigger": "parent_company_legal",
                    "subject": parent,
                    "outlet_name": outlet,
                    "parent_company": parent,
                    "packet": pkt,
                    "fetch_params": params,
                    "courtlistener_case_name": case,
                    "courtlistener_url": top.get("url"),
                },
            )

    if meta_status == "results_found" and top_advertisers:
        ad_queries = 0
        for adv in top_advertisers:
            if ad_queries >= 2:
                break
            an = str(adv.get("name") or "").strip()
            if not an or an.lower() == "unknown":
                continue
            rows = await _courtlistener_opinion_hits(an, limit=1)
            ad_queries += 1
            if not rows:
                continue
            spend = adv.get("spend_upper_bound_sum_est")
            amt: float | None = None
            if isinstance(spend, (int, float)) and spend > 0:
                amt = float(spend)
            charge_st = "under investigation" if advertiser_conflict_flag else None
            params = proportionality_fetch_params_dict(
                category="political",
                violation_type="campaign finance",
                charge_status=charge_st,
                amount_involved=amt,
            )
            pkt = await fetch_proportionality_packet(
                category=params["category"],
                violation_type=params["violation_type"],
                charge_status=params["charge_status"],
                amount_involved=params["amount_involved"],
            )
            records.append(
                {
                    "trigger": "ad_buy",
                    "subject": an,
                    "outlet_name": outlet,
                    "parent_company": parent or None,
                    "packet": pkt,
                    "fetch_params": params,
                    "courtlistener_case_name": str(rows[0].get("case_name") or "").strip() or None,
                },
            )

    return records


async def enrich_outlet_dossier_for_article(
    outlet_display: str,
    domain: str,
    article_topic: str | None,
) -> dict[str, Any]:
    """Async: Wikipedia + Claude ownership hint + Meta political/issue ads."""
    pub = lookup_domain(domain) or {}
    outlet_name = str(pub.get("name") or outlet_display or domain or "unknown").strip()
    parent = parent_company_for_domain(domain)
    ownership_note: str | None = None

    if not parent:
        wiki_text, _wiki_title = _wikipedia_summary_extract(outlet_name)
        if not wiki_text and domain:
            wiki_text, _ = _wikipedia_summary_extract(domain.split(".")[0].replace("-", " ").title())
        if wiki_text:
            extracted = _claude_parent_from_summary(wiki_text, outlet_name)
            parent = extracted.get("parent_company") or parent
            ownership_note = extracted.get("ownership_note")

    search_terms = [s for s in {domain, outlet_name} if s and len(s) > 2]
    meta_combined: dict[str, Any] = {"status": "skipped"}
    for st in search_terms[:2]:
        meta_combined = await query_ad_library(st, country="US", limit=20)
        if meta_combined.get("status") == "results_found":
            break

    top_advertisers = _aggregate_advertisers(meta_combined)
    conflict, conflict_note = _advertiser_stake_conflict(article_topic, top_advertisers)

    proportionality_records: list[dict[str, Any]] = []
    try:
        proportionality_records = await _collect_outlet_proportionality_records(
            outlet_name,
            parent,
            top_advertisers,
            str(meta_combined.get("status") or ""),
            conflict,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[outlet_dossier_article] proportionality: %s", exc)
        proportionality_records = []

    return {
        "outlet": outlet_name,
        "domain": domain,
        "parent_company": parent,
        "ownership_note": ownership_note,
        "registry_match": bool(pub),
        "top_advertisers": top_advertisers,
        "advertiser_conflict_flag": conflict,
        "advertiser_conflict_note": conflict_note,
        "ad_library_status": meta_combined.get("status"),
        "method_note": "Meta results are political/issue ads only; not all commercial advertisers.",
        "proportionality_records": proportionality_records,
    }
