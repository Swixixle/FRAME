"""
Absence / sibling-outlet hints from a comparative coverage set.

Lives beside `comparative_coverage` so the waterfall module stays focused on retrieval only.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from publisher_registry import parent_company_for_domain


def _domain_from_coverage_article(a: dict[str, Any]) -> str:
    u = (a.get("url") or "").strip()
    if u:
        try:
            return (urlparse(u).netloc or "").lower().replace("www.", "")
        except Exception:  # noqa: BLE001
            pass
    d = (a.get("domain") or "").strip().lower().replace("www.", "")
    return d


def compute_absence_signal(
    article: dict[str, Any],
    coverage_full: dict[str, Any] | None,
    outlet_dossier: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Coverage-set and sibling-outlet hints. Domain match only — not proof of editorial avoidance.
    """
    articles = (coverage_full or {}).get("articles") or []
    if not isinstance(articles, list):
        articles = []
    n = len(articles)
    primary_url = str(article.get("url") or "")
    primary_domain = ""
    try:
        primary_domain = (urlparse(primary_url).netloc or "").lower().replace("www.", "")
    except Exception:  # noqa: BLE001
        primary_domain = ""
    pub = str(article.get("publication") or "").lower().replace("www.", "")

    outlet_in = False
    cov_domains: list[str] = []
    for row in articles:
        if not isinstance(row, dict):
            continue
        d = _domain_from_coverage_article(row)
        if d:
            cov_domains.append(d)
        if primary_domain and d == primary_domain:
            outlet_in = True
        if pub and d and (pub in d or d in pub):
            outlet_in = True

    parent = None
    if isinstance(outlet_dossier, dict):
        parent = outlet_dossier.get("parent_company") or None
    if not parent:
        parent = parent_company_for_domain(primary_domain)

    sibling_domains: list[str] = []
    if parent and n >= 5:
        domain_to_parent: dict[str, str] = {}
        for d in set(cov_domains):
            p = parent_company_for_domain(d)
            if p:
                domain_to_parent[d] = p
        same_parent = [d for d, p in domain_to_parent.items() if p == parent]
        sibling_domains = [d for d in same_parent if d and d != primary_domain][:12]

    sibling_div = bool(parent and len(sibling_domains) >= 1 and n >= 5)

    gap_parts: list[str] = []
    if n >= 5 and not outlet_in:
        gap_parts.append(
            f"Comparative index returned {n} articles; this outlet’s domain was not among them "
            "(URL/domain match only; index may be incomplete)."
        )
    elif n >= 5 and outlet_in:
        gap_parts.append("This outlet’s domain appears in the comparative coverage set for this query window.")

    if sibling_div and parent:
        gap_parts.append(
            f"Other outlets mapped to the same parent company ({parent}) appear in this coverage set: "
            f"{', '.join(sibling_domains[:5])}. Compare those pieces independently."
        )

    return {
        "outlets_covering": n,
        "outlet_in_coverage_set": outlet_in,
        "sibling_outlet_divergence": sibling_div,
        "sibling_outlets": sibling_domains,
        "gap_note": " ".join(gap_parts) if gap_parts else None,
    }
