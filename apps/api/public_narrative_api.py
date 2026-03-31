"""
Public Narrative + Global Perspectives layer.
Given a claim or narrative, returns how different regional media ecosystems
are framing the same story — with divergence points and what nobody is saying.
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

Be precise and specific. Do not be neutral to the point of uselessness. Name the actual framing differences. If Russian state media frames something as Western aggression and Western media frames it as Russian aggression, say that clearly.

Return ONLY valid JSON. No preamble. No markdown fences.

Format:
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
      "confidence_note": "brief note on how reliable this characterization is"
    }
  ],
  "divergence_points": [
    "specific point where ecosystem framings directly conflict"
  ],
  "consensus_elements": [
    "factual element that all ecosystems agree on"
  ],
  "absent_from_all": [
    "important angle, voice, or fact that no major ecosystem is covering"
  ],
  "most_divergent_pair": {
    "ecosystem_a": "id",
    "ecosystem_b": "id",
    "reason": "why these two framings are most irreconcilable"
  }
}

Ecosystems to analyze:
__ECOSYSTEMS_JSON__

Narrative to analyze:
__NARRATIVE__"""


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
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        result: dict[str, Any] = json.loads(raw)
        result["source"] = "model_knowledge"
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
            "error": str(e),
        }


# Keep backward compat — old endpoint used run_public_narrative
run_public_narrative = run_global_perspectives
