"""
Parallel enrichment → Claude (sonnet structure, opus narrative) → persist dossier.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import anthropic

from db import save_dossier
from enrichment import charitable, courtlistener, fec, opensecrets, sec, socialblade, statements
from models.dossier import (
    Case,
    CharitableRecord,
    Contribution,
    DossierSchema,
    Statement,
)
from models.entity import ResolvedEntity

logger = logging.getLogger(__name__)

AUDITOR_SYSTEM = """You are a neutral forensic auditor for public-record alignment. You output structured factual records only: no verdict, no spin, no moral judgment. Do not use adjectives except where they denote measurable quantities (e.g. "three", "$1.2M"). Every assertion must map to a cited source id or be placed in `unknowns`. If data is missing, say so explicitly. Never infer intent from patterns alone."""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


async def _run_labeled(
    label: str,
    coro: Any,
    sources: list[dict[str, Any]],
    unknowns: list[str],
) -> tuple[str, Any]:
    try:
        val = await coro
        sources.append({"id": label, "status": "ok"})
        return label, val
    except Exception as exc:  # noqa: BLE001
        msg = f"failed: {exc}"
        sources.append({"id": label, "status": f"failed: {msg}"})
        unknowns.append(f"{label} enrichment failed: {msg}")
        logger.exception("%s failed", label)
        return label, None


async def assemble_dossier(frame_id: str, entity: ResolvedEntity) -> DossierSchema:
    sources: list[dict[str, Any]] = []
    unknowns: list[str] = []

    jobs: list[Any] = [
        _run_labeled(
            "charitable",
            charitable.get_charitable_record(entity.canonical_name, ein=entity.ein),
            sources,
            unknowns,
        ),
        _run_labeled(
            "courtlistener",
            courtlistener.search_cases(entity.canonical_name),
            sources,
            unknowns,
        ),
        _run_labeled(
            "statements",
            statements.search_statements(entity.canonical_name),
            sources,
            unknowns,
        ),
    ]

    if entity.type in ("politician", "corporate_exec"):
        jobs.extend(
            [
                _run_labeled(
                    "fec_contributions",
                    fec.get_contributions(entity.canonical_name),
                    sources,
                    unknowns,
                ),
                _run_labeled(
                    "fec_expenditures",
                    fec.get_expenditures(entity.canonical_name),
                    sources,
                    unknowns,
                ),
                _run_labeled(
                    "opensecrets",
                    opensecrets.get_summary(entity.canonical_name),
                    sources,
                    unknowns,
                ),
            ]
        )

    if entity.type == "corporate_exec":
        jobs.append(
            _run_labeled(
                "sec_search",
                sec.search_company(entity.canonical_name),
                sources,
                unknowns,
            )
        )
        if entity.sec_cik:
            jobs.append(
                _run_labeled(
                    "sec_filings",
                    sec.get_filings_for_cik(entity.sec_cik),
                    sources,
                    unknowns,
                )
            )

    if entity.type in ("influencer", "podcaster"):
        jobs.append(
            _run_labeled(
                "socialblade",
                socialblade.get_channel_metrics(entity.canonical_name),
                sources,
                unknowns,
            )
        )

    labeled = await asyncio.gather(*jobs)
    raw_bundle: dict[str, Any] = {"entity": entity.model_dump(), "frame_id": frame_id}
    for label, val in labeled:
        raw_bundle[label] = val

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    sonnet_model = os.environ.get("CLAUDE_SONNET_MODEL", "claude-sonnet-4-20250514")
    opus_model = os.environ.get("CLAUDE_OPUS_MODEL", "claude-opus-4-5-20250514")

    dossier: DossierSchema | None = None

    if key:
        client = anthropic.AsyncAnthropic(api_key=key)
        user_prompt = (
            "Given the following JSON enrichment bundle, output ONLY valid JSON matching "
            "DossierSchema fields: frame_id, entity_canonical_name, entity_type, contributions, "
            "expenditures, cases, statements, policy_chains, sponsors, charitable, sec_filings, "
            "social_metrics, sources, unknowns, narrative_summary (empty string for now). "
            "Map lists of dicts into Contribution/Case/Statement models where applicable.\n\n"
            + json.dumps(raw_bundle, default=str, ensure_ascii=False)
        )
        try:
            msg = await client.messages.create(
                model=sonnet_model,
                max_tokens=8192,
                system=AUDITOR_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "text", None))
            data = _extract_json_object(text)
            dossier = DossierSchema.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude sonnet dossier structuring failed: %s", exc)
            unknowns.append(f"sonnet structuring: {exc}")

    if dossier is None:
        contributions: list[Contribution] = []
        raw_c = raw_bundle.get("fec_contributions")
        if isinstance(raw_c, list):
            for x in raw_c:
                if isinstance(x, Contribution):
                    contributions.append(x)
                elif isinstance(x, dict):
                    try:
                        contributions.append(Contribution.model_validate(x))
                    except Exception:  # noqa: BLE001
                        continue
        ch = CharitableRecord()
        if isinstance(raw_bundle.get("charitable"), CharitableRecord):
            ch = raw_bundle["charitable"]
        elif isinstance(raw_bundle.get("charitable"), dict):
            try:
                ch = CharitableRecord.model_validate(raw_bundle["charitable"])
            except Exception:  # noqa: BLE001
                pass

        cases: list[Case] = []
        cl = raw_bundle.get("courtlistener")
        if isinstance(cl, list):
            for i, row in enumerate(cl[:20]):
                if isinstance(row, dict):
                    cases.append(
                        Case(
                            name=str(row.get("caseName") or row.get("absolute_url") or f"case-{i}"),
                            court=str(row.get("court") or "") or None,
                            source_url=str(row.get("absolute_url") or "") or None,
                        )
                    )

        stmts: list[Statement] = []
        st = raw_bundle.get("statements")
        if isinstance(st, list):
            for row in st[:20]:
                if isinstance(row, dict):
                    stmts.append(
                        Statement(
                            text=str(row.get("title") or row.get("description") or "")[:2000],
                            source_url=str(row.get("url") or "") or None,
                        )
                    )

        dossier = DossierSchema(
            frame_id=frame_id,
            entity_canonical_name=entity.canonical_name,
            entity_type=entity.type,
            contributions=contributions,
            expenditures=list(raw_bundle["fec_expenditures"])
            if isinstance(raw_bundle.get("fec_expenditures"), list)
            else [],
            cases=cases,
            statements=stmts,
            charitable=ch,
            sec_filings=list(raw_bundle["sec_filings"])
            if isinstance(raw_bundle.get("sec_filings"), list)
            else [],
            social_metrics=raw_bundle.get("socialblade")
            if isinstance(raw_bundle.get("socialblade"), dict)
            else None,
            sources=sources,
            unknowns=unknowns,
            narrative_summary="",
        )

    narrative = ""
    if key:
        try:
            client = anthropic.AsyncAnthropic(api_key=key)
            msg2 = await client.messages.create(
                model=opus_model,
                max_tokens=4096,
                system=AUDITOR_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": "Write only the field narrative_summary: chronological, complete, "
                        "no omissions, no adjectives unless measurements. Respond with a JSON object "
                        "with a single key narrative_summary.\n\n"
                        + dossier.model_dump_json(),
                    }
                ],
            )
            text2 = "".join(b.text for b in msg2.content if getattr(b, "text", None))
            try:
                nj = _extract_json_object(text2)
                narrative = str(nj.get("narrative_summary", ""))
            except Exception:  # noqa: BLE001
                narrative = text2[:8000]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude opus narrative failed: %s", exc)
            unknowns.append(f"opus narrative: {exc}")

    if narrative:
        dossier.narrative_summary = narrative

    dossier.sources = sources
    dossier.unknowns = list(dict.fromkeys([*dossier.unknowns, *unknowns]))

    await save_dossier(dossier)
    return dossier
