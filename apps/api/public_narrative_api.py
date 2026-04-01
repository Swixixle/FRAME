"""
Public Narrative + Global Perspectives layer.
Given a claim or narrative, returns how different regional media ecosystems
are framing the same story — with reasoning layer, absence detail, and leads.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

MEDIA_ECOSYSTEMS = [
    {
        "id": "western_anglophone",
        "label": "Western / Anglophone",
        "outlets": ["AP News", "Reuters", "BBC", "New York Times", "Washington Post"],
    },
    {
        "id": "russian_state",
        "label": "Russian / state media",
        "outlets": ["RT", "TASS", "Pravda", "Sputnik"],
    },
    {
        "id": "iranian_regional",
        "label": "Iranian / regional",
        "outlets": ["PressTV", "Islamic Republic News Agency", "Tasnim News"],
    },
    {
        "id": "chinese_state",
        "label": "Chinese / state media",
        "outlets": ["Xinhua", "CGTN", "Global Times", "People's Daily"],
    },
    {
        "id": "arab_gulf",
        "label": "Arab / Gulf",
        "outlets": ["Al Jazeera", "Al Arabiya", "Gulf News", "Middle East Eye"],
    },
    {
        "id": "israeli",
        "label": "Israeli",
        "outlets": ["Haaretz", "Times of Israel", "Jerusalem Post", "Ynet"],
    },
    {
        "id": "south_asian",
        "label": "South Asian",
        "outlets": ["Dawn (Pakistan)", "The Hindu", "Hindustan Times", "Daily Star (Bangladesh)"],
    },
    {
        "id": "european",
        "label": "European",
        "outlets": ["Der Spiegel", "Le Monde", "El País", "Euronews"],
    },
]

GLOBAL_PERSPECTIVES_PROMPT = """You are a global media framing analyst for a public record verification system.

__COVERAGE_BLOCK__

Given a narrative or claim, analyze how different regional media ecosystems are framing this story.

For each ecosystem, analyze how the listed outlets typically cover this type of story based on their documented editorial positions, state affiliations, and historical coverage patterns.

Be precise and specific. Do not be neutral to the point of uselessness. Name the actual framing differences.

Return ONLY valid JSON. No preamble. No markdown fences.

Schema (all keys required; use empty arrays/objects where unknown):

{
  "claim": "the core claim being analyzed in one sentence",
  "ecosystems": [
    {
      "id": "ecosystem_id",
      "label": "ecosystem label",
      "outlets": ["outlet1", "outlet2"],
      "framing": "2-3 sentence description of how this ecosystem frames this story",
      "key_language": ["specific word or phrase choices", "that distinguish this framing"],
      "emphasized": "what this ecosystem emphasizes",
      "minimized": "what this ecosystem downplays or omits",
      "confidence_tier": "official_primary|official_secondary|single_source|structural_heuristic",
      "confidence_note": "brief note on how reliable this characterization is",
      "trigger_phrases": ["3-5 exact phrases readers would see in this ecosystem on this story"],
      "example_headlines": [
        {"text": "headline text", "source": "Reuters or inferred", "type": "retrieved|inferred"}
      ]
    }
  ],
  "divergence_points": ["specific point where ecosystem framings directly conflict"],
  "consensus_elements": ["factual element that all ecosystems agree on"],
  "absent_from_all": [
    {
      "topic": "absent topic in plain English",
      "absence_reason": "too_new|too_niche|avoided|poorly_indexed|unknown",
      "why_it_matters": "one sentence on why this absence is significant",
      "suggested_query": "3-5 word search string to find this angle",
      "suggested_sources": ["OpenSecrets", "FEC", "CourtListener", "Congressional Record"]
    }
  ],
  "most_divergent_pair": {
    "ecosystem_a": "id",
    "ecosystem_b": "id",
    "reason": "why these two framings are most irreconcilable"
  },
  "reasoning_summary": "2-3 sentences: what linguistic or framing evidence most influenced divergence; strongest signal that ecosystems tell different stories",
  "confidence_breakdown": {
    "pct_directly_cited": 0,
    "pct_inferred": 0,
    "pct_consensus": 0,
    "pct_contested": 0,
    "primary_evidence_type": "retrieved_articles|outlet_patterns|mixed"
  },
  "investigative_leads": [
    {
      "action": "Search CourtListener for",
      "target": "specific query or entity",
      "reason": "why this matters",
      "url_hint": "optional URL pattern"
    }
  ],
  "confidence_note": "Overall note on reliability of this analysis"
}

Rules for absent_from_all: each item MUST be an object with topic, absence_reason, why_it_matters, suggested_query, suggested_sources (array of strings). absence_reason must be one of: too_new, too_niche, avoided, poorly_indexed, unknown.

Rules for example_headlines: type is "retrieved" only if the headline clearly came from the coverage block above; otherwise "inferred".

Rules for confidence_breakdown: integers 0-100; pct_directly_cited + pct_inferred should sum to 100; pct_consensus + pct_contested should sum to 100.

Rules for investigative_leads: 3-5 objects with concrete actions (OpenSecrets, FEC, CourtListener, Congressional Record, GDELT, FOIA) where relevant.

Ecosystems to analyze:
__ECOSYSTEMS_JSON__

Narrative to analyze:
__NARRATIVE__"""


def _normalize_global_perspectives(result: dict[str, Any]) -> dict[str, Any]:
    """Ensure new fields exist; keep legacy string-only absent_from_all entries."""
    eco_list = result.get("ecosystems")
    if isinstance(eco_list, list):
        for eco in eco_list:
            if not isinstance(eco, dict):
                continue
            if "trigger_phrases" not in eco:
                eco["trigger_phrases"] = []
            if "example_headlines" not in eco:
                eco["example_headlines"] = []
    absent = result.get("absent_from_all")
    if isinstance(absent, list):
        norm_abs: list[Any] = []
        for item in absent:
            if isinstance(item, str) and item.strip():
                norm_abs.append(item.strip())
            elif isinstance(item, dict):
                norm_abs.append(item)
        result["absent_from_all"] = norm_abs
    if "reasoning_summary" not in result:
        result["reasoning_summary"] = ""
    if "confidence_breakdown" not in result or not isinstance(result.get("confidence_breakdown"), dict):
        result["confidence_breakdown"] = {}
    if "investigative_leads" not in result or not isinstance(result.get("investigative_leads"), list):
        result["investigative_leads"] = []
    return result


def run_global_perspectives(narrative: str, coverage_context: str = "") -> dict[str, Any]:
    """
    Use Claude to analyze how this narrative is being framed
    across regional media ecosystems worldwide.
    """
    text = (narrative or "").strip()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return {
            "claim": text[:200],
            "ecosystems": [],
            "divergence_points": [],
            "consensus_elements": [],
            "absent_from_all": [],
            "most_divergent_pair": None,
            "reasoning_summary": "",
            "confidence_breakdown": {},
            "investigative_leads": [],
            "error": "ANTHROPIC_API_KEY not set",
        }

    client = anthropic.Anthropic(api_key=key)

    ecosystems_json = json.dumps(
        [{"id": e["id"], "label": e["label"], "outlets": e["outlets"]} for e in MEDIA_ECOSYSTEMS],
        indent=2,
    )
    cc = (coverage_context or "").strip()
    grounded = bool(cc)
    logger.info("[PERSPECTIVES] grounded=%s", grounded)
    if cc:
        coverage_block = (
            "The following sources were retrieved and verified to cover this story. "
            "Use these as the factual basis for identifying which outlets are on each side. "
            "Do not invent outlets or attribute positions to sources not listed here.\n\n"
            + cc
        )
    else:
        coverage_block = (
            "No comparative coverage was retrieved for this story. "
            "Base the analysis only on the original article. "
            "Do not fabricate outlet names or positions."
        )
    prompt = (
        GLOBAL_PERSPECTIVES_PROMPT.replace("__COVERAGE_BLOCK__", coverage_block)
        .replace("__ECOSYSTEMS_JSON__", ecosystems_json)
        .replace("__NARRATIVE__", text[:4000])
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        result: dict[str, Any] = json.loads(raw)
        result = _normalize_global_perspectives(result)
        result["source"] = "model_knowledge"
        if not (result.get("confidence_note") or "").strip():
            result["confidence_note"] = (
                "Framing analysis based on documented editorial positions and historical "
                "coverage patterns of named outlets. Characterizations reflect general "
                "tendencies, not any specific article. Verify against live sources."
            )
        return result
    except json.JSONDecodeError as e:
        return {
            "claim": text[:200],
            "ecosystems": [],
            "divergence_points": [],
            "consensus_elements": [],
            "absent_from_all": [],
            "most_divergent_pair": None,
            "reasoning_summary": "",
            "confidence_breakdown": {},
            "investigative_leads": [],
            "error": f"Parse error: {e}",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "claim": text[:200],
            "ecosystems": [],
            "divergence_points": [],
            "consensus_elements": [],
            "absent_from_all": [],
            "most_divergent_pair": None,
            "reasoning_summary": "",
            "confidence_breakdown": {},
            "investigative_leads": [],
            "error": str(e),
        }


def generate_contextual_brief(
    article_topic: str,
    article_title: str,
    named_entities: list[str],
    coverage_context: str = "",
) -> dict[str, Any]:
    """
    Epistemics-disciplined contextual brief: FACT / INFERRED / contradiction separation.
    Call via asyncio.to_thread.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return {}

    entities_str = ", ".join(named_entities[:10]) if named_entities else "none"
    cc = (coverage_context or "").strip()
    coverage_block = f"\nRelated coverage context:\n{cc}\n" if cc else ""

    prompt = f"""You are a rigorous senior analyst briefing an investigative journalist.

Hard rules:
- Every typed datum uses exactly one of: FACT, INFERRED, or (for contradictions) plain Claim vs Record — never fuse FACT and INFERRED in the same sentence.
- stakes must be FACT-only sentences (documentable consequences if the claim were true). Put interpretations only in impact_signals rows marked INFERRED.
- Never invent sources, quotes, or statistics. Omit rather than fabricate.

HEADLINE: {article_title}
STORY: {article_topic}
KEY ENTITIES: {entities_str}
{coverage_block}

Return this exact JSON structure. JSON only — no markdown, no text outside the JSON.

{{
  "claim_type": "EVENT" | "STATEMENT" | "PREDICTION" | "ALLEGATION" | "POLICY",

  "why_it_matters": {{
    "stakes": "1-2 sentences, FACT only — immediate consequences if the core claim were true.",
    "impact_signals": [
      {{
        "signal": "one observable datapoint only (e.g. price move) — no interpretation mixed in",
        "source": "named publication or data source",
        "timestamp": "date or recent",
        "type": "FACT" | "INFERRED"
      }}
    ],
    "urgency": "immediate" | "days" | "weeks" | "long-term"
  }},

  "historical_precedent": {{
    "case": "specific named event",
    "date": "year or period",
    "trigger": "what caused it — 1 sentence, FACT",
    "escalation_pattern": "how it developed — 1 sentence",
    "resolution_mechanism": "what ended it — 1 sentence",
    "resolution_timeline": "how long it took",
    "delta": {{
      "military_posture": "difference vs now",
      "actor_alignment": "difference vs now",
      "information_environment": "difference vs now"
    }},
    "breakpoint": "where the analogy fails — most important difference",
    "confidence": "high" | "medium" | "low"
  }},

  "downstream_implications": {{
    "expected": [
      {{
        "domain": "energy" | "markets" | "military" | "humanitarian" | "legal" | "policy" | "elections" | "public health",
        "if_claim_holds": "one sentence — must match the row type field",
        "direction": "positive" | "negative" | "uncertain",
        "timeframe": "immediate" | "30 days" | "6 months" | "long-term",
        "type": "FACT" | "INFERRED"
      }}
    ],
    "observed": [
      {{
        "domain": "string",
        "current_reality": "what is happening now",
        "source": "named source",
        "type": "FACT"
      }}
    ],
    "contradictions": [
      {{
        "claim": "what the article or speaker claims",
        "reality": "what the observable record shows",
        "significance": "why the gap matters"
      }}
    ]
  }},

  "analyst_signals": [
    {{
      "source": "real named institution or analyst",
      "model_type": "market analysis" | "policy analysis" | "economic model" | "military assessment" | "legal analysis",
      "signal": "paraphrase only — no fabricated quotes",
      "date": "date or recent",
      "url": "direct https URL if known, else empty string",
      "confidence": "PRIMARY" | "SECONDARY" | "INFERRED",
      "excerpt_note": "document or report reference if known, else empty"
    }}
  ],

  "comparable_moment": {{
    "headline": "newspaper-style headline for the historical moment",
    "then": {{
      "trigger": "what started it",
      "dynamics": "how it played out",
      "timeline": "how long"
    }},
    "now": {{
      "current_signals": "observable today",
      "actor_alignment": "who controls what"
    }},
    "pattern": "repeating dynamic — 1 sentence",
    "breakpoint": "mandatory — where this analogy breaks down"
  }},

  "investigative_hooks": {{
    "next_questions": [
      "specific unanswered question for a journalist"
    ],
    "next_actions": [
      {{
        "action": "specific step",
        "where": "named database or method (e.g. CourtListener, GDELT, AIS shipping data, OpenSecrets)",
        "why": "what this would reveal"
      }}
    ]
  }}
}}

Rules:
- impact_signals: real datapoints with sources; omit if not citable.
- contradictions: only genuine observable conflicts; omit if none.
- breakpoint fields in historical_precedent and comparable_moment are mandatory when those objects are non-empty.
- next_actions: name specific systems (not vague "check sources").
- Empty arrays/objects when no confident content.
- JSON only."""

    client = anthropic.Anthropic(api_key=key)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw.strip())
        return result if isinstance(result, dict) else {}
    except Exception as e:  # noqa: BLE001
        logger.warning("[CONTEXT_BRIEF] %s", e)
        return {}


# Keep backward compat — old endpoint used run_public_narrative
run_public_narrative = run_global_perspectives
