"""Public facade for Perplexity Layer B (delegates to ``perplexity_layer_b``)."""

from __future__ import annotations

from typing import Any


async def build_journalist_layer_b(
    *,
    name: str,
    topic: str,
    publication: str,
    quoted_sources: list[dict[str, Any]],
    max_source_audits: int = 3,
) -> dict[str, Any]:
    from perplexity_layer_b import build_journalist_layer_b as _build

    t = (topic or "").strip()
    return await _build(
        display_name=name,
        publication=publication,
        article_topic=t or None,
        quoted_sources=quoted_sources,
        max_source_audits=max_source_audits,
    )


async def build_outlet_layer_b(
    *,
    outlet_name: str,
    domain: str | None,
    registry_match: bool,
) -> dict[str, Any]:
    from perplexity_layer_b import build_outlet_layer_b as _build

    return await _build(
        outlet_name=outlet_name,
        domain=domain,
        registry_match=registry_match,
    )
