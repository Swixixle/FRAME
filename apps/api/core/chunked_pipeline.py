"""
Chunked parallel pipeline for long-form audio: split → transcribe → claim extract → dedupe → entity coordination.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import uuid
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from adapters_podcast import extract_speaker_claims, probe_audio_duration_seconds, transcribe_audio

logger = logging.getLogger(__name__)


class ChunkStrategy(BaseModel):
    n_chunks: int
    method: str  # "single" | "parallel" | "parallel_coordinated"


class CanonicalEntity(BaseModel):
    canonical_name: str
    entity_type: str  # "person" | "organization" | "place" | "legislation"
    aliases: list[str] = Field(default_factory=list)
    chunk_mentions: list[int] = Field(default_factory=list)
    first_mention_chunk: int = 0
    claim_count: int = 0


class ChunkResult(BaseModel):
    chunk_index: int
    transcript: str
    claims: list[dict[str, Any]]
    entities: list[str]


def get_chunk_strategy(duration_seconds: int) -> ChunkStrategy:
    if duration_seconds < 300:
        return ChunkStrategy(n_chunks=1, method="single")
    if duration_seconds < 1800:
        return ChunkStrategy(n_chunks=2, method="parallel")
    if duration_seconds < 7200:
        return ChunkStrategy(n_chunks=3, method="parallel")
    return ChunkStrategy(n_chunks=4, method="parallel_coordinated")


def split_audio(input_path: str, n_chunks: int, overlap_seconds: int = 30) -> list[str]:
    """Split audio into n_chunks via ffmpeg; outputs under /tmp/."""
    total_duration = probe_audio_duration_seconds(input_path)
    if total_duration is None or total_duration <= 0:
        raise ValueError("Could not determine audio duration for splitting")
    chunk_dur = total_duration / n_chunks
    out_paths: list[str] = []
    try:
        for i in range(n_chunks):
            start = max(0.0, i * chunk_dur - (overlap_seconds if i > 0 else 0))
            end = min(
                total_duration,
                (i + 1) * chunk_dur + (overlap_seconds if i < n_chunks - 1 else 0),
            )
            if end <= start:
                continue
            uid = uuid.uuid4().hex[:12]
            out = f"/tmp/frame_chunk_{i}_{uid}.mp3"
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    input_path,
                    "-ss",
                    str(start),
                    "-to",
                    str(end),
                    "-c",
                    "copy",
                    out,
                ],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg split failed for chunk {i}: {(proc.stderr or proc.stdout or '')[:400]}"
                )
            out_paths.append(out)
        if len(out_paths) != n_chunks:
            raise RuntimeError(f"Expected {n_chunks} chunk files, got {len(out_paths)}")
        return out_paths
    except Exception:
        for p in out_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        raise


async def transcribe_chunk(chunk_path: str, chunk_index: int) -> tuple[int, str]:
    """Same faster-whisper path as adapters_podcast.transcribe_audio (via thread pool)."""
    d = await asyncio.to_thread(transcribe_audio, chunk_path)
    return chunk_index, d.get("full_text") or ""


async def extract_claims_chunk(
    transcript: str,
    chunk_index: int,
    precontext: str = "",
) -> ChunkResult:
    pseudo = {"full_text": transcript, "segments": []}
    title = f"{precontext} — chunk {chunk_index}" if precontext else f"chunk {chunk_index}"
    claims = await asyncio.to_thread(
        extract_speaker_claims,
        pseudo,
        title,
        chunk_index=chunk_index,
    )
    entities: list[str] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        for e in c.get("entities") or []:
            s = str(e).strip()
            if len(s) > 2:
                entities.append(s)
    seen: set[str] = set()
    uniq_entities: list[str] = []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            uniq_entities.append(e)
    return ChunkResult(
        chunk_index=chunk_index,
        transcript=transcript,
        claims=claims,
        entities=uniq_entities,
    )


def _normalize_claim_text(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def deduplicate_claims(chunk_results: list[ChunkResult]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for cr in chunk_results:
        for c in cr.claims:
            if not isinstance(c, dict):
                continue
            raw = str(c.get("text") or "").strip()
            if not raw:
                continue
            norm = _normalize_claim_text(raw)
            if not norm:
                continue
            dup_at: int | None = None
            for j, existing in enumerate(kept):
                if _normalize_claim_text(str(existing.get("text") or "")) == norm:
                    dup_at = j
                    break
            if dup_at is None:
                nc = dict(c)
                nc["source_chunks"] = [cr.chunk_index]
                kept.append(nc)
            else:
                sc = kept[dup_at].get("source_chunks")
                if not isinstance(sc, list):
                    sc = [cr.chunk_index]
                elif cr.chunk_index not in sc:
                    sc = list(sc) + [cr.chunk_index]
                    sc = sorted(set(sc))
                kept[dup_at]["source_chunks"] = sc
    return kept


async def semantic_deduplicate_claims(
    claims: list[dict[str, Any]],
    episode_title: str = "",
) -> list[dict[str, Any]]:
    """
    Pass 2 semantic dedup: merge claims that assert the same fact differently.

    Only runs when there are >10 claims (below that, exact dedup is enough).
    Returns the original list unchanged if API call fails.
    """
    if len(claims) <= 10:
        return claims

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return claims

    sonnet = os.environ.get("CLAUDE_SONNET_MODEL", "claude-sonnet-4-20250514")

    compact = [
        {
            "id": i,
            "text": str(c.get("text", ""))[:300],
            "type": c.get("type", "general"),
            "chunks": c.get("source_chunks", []),
            "risk": c.get("implication_risk", "low"),
        }
        for i, c in enumerate(claims)
    ]

    prompt = f"""You are deduplicating factual claims extracted from a podcast episode.
Episode: {episode_title or "unknown"}
Total claims: {len(compact)}

Claims (JSON):
{json.dumps(compact, ensure_ascii=False)}

Task:
- Identify groups of claims that assert the same underlying fact,
  even if worded differently.
- For each group, keep the most specific and complete version.
- Flag any claims that directly contradict each other with
  "contradiction": true on the kept claim.
- Do NOT merge claims that are related but distinct (e.g., two
  different financial figures about the same entity).
- Preserve all claims that are unique.

Return ONLY a JSON array of claim IDs to keep (from the "id" field above).
Example: [0, 2, 5, 7, 11]
No markdown. No explanation. Just the array.
"""

    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        msg = await client.messages.create(
            model=sonnet,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") or ""
            for b in msg.content
            if getattr(b, "text", None) is not None
        ).strip()

        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
        text = text.strip()

        keep_ids = json.loads(text)
        if not isinstance(keep_ids, list):
            return claims

        keep_set: set[int] = set()
        for i in keep_ids:
            if isinstance(i, bool):
                continue
            if isinstance(i, int):
                keep_set.add(i)
            elif isinstance(i, float) and i == int(i):
                keep_set.add(int(i))

        result = [c for j, c in enumerate(claims) if j in keep_set]

        logger.info(
            "semantic_deduplicate_claims: %d → %d claims (removed %d)",
            len(claims),
            len(result),
            len(claims) - len(result),
        )
        return result if result else claims

    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic_deduplicate_claims failed: %s", exc)
        return claims


async def coordinate_entities(chunk_results: list[ChunkResult]) -> list[CanonicalEntity]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or not chunk_results:
        return []
    sonnet = os.environ.get("CLAUDE_SONNET_MODEL", "claude-sonnet-4-20250514")
    payload = [
        {"chunk_index": cr.chunk_index, "entities": cr.entities, "claim_count": len(cr.claims)}
        for cr in chunk_results
    ]
    n = len(chunk_results)
    prompt = f"""You are deduplicating entities from {n} parallel chunks of the same audio.

Entities by chunk: {json.dumps(payload, ensure_ascii=False)}

Return ONLY a JSON array of canonical entities:
[{{
    "canonical_name": "full legal name",
    "entity_type": "person|organization|place|legislation",
    "aliases": ["all name variants found"],
    "chunk_mentions": [0, 1, 2],
    "first_mention_chunk": 0,
    "claim_count": 4
}}]

Rules:
- Merge variants: 'Rand Paul', 'Senator Paul', 'Paul' → one entity
- Do NOT merge different people who share a surname
- Return valid JSON array only, no markdown
"""
    client = anthropic.AsyncAnthropic(api_key=key)
    try:
        msg = await client.messages.create(
            model=sonnet,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") or "" for b in msg.content if getattr(b, "text", None)
        )
        raw = text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
                if raw.startswith("json"):
                    raw = raw[4:]
        data = json.loads(raw.strip())
        if not isinstance(data, list):
            return []
        out: list[CanonicalEntity] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                out.append(CanonicalEntity.model_validate(row))
            except Exception:  # noqa: BLE001
                continue
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("coordinate_entities failed: %s", exc)
        return []


def _parallel_limit(tier_config: Any | None, default: int) -> int:
    if tier_config is None:
        return default
    try:
        n = int(getattr(tier_config, "n_parallel_chunks", None) or default)
    except (TypeError, ValueError):
        n = default
    return max(1, n)


async def _gather_with_semaphore(
    coros: list[Any],
    limit: int,
) -> list[Any]:
    sem = asyncio.Semaphore(limit)

    async def _run(c: Any) -> Any:
        async with sem:
            return await c

    return await asyncio.gather(*[_run(c) for c in coros])


async def process_chunked_audio(
    audio_path: str,
    duration_seconds: float,
    precontext: str = "",
    tier_config: Any | None = None,
) -> dict[str, Any] | None:
    """
    Run split → parallel transcribe → parallel claim extract → dedupe → coordinate entities.
    Returns None when strategy is single (caller should use existing one-shot pipeline).
    """
    strategy = get_chunk_strategy(int(duration_seconds))
    if strategy.method == "single":
        return None

    n_chunks = strategy.n_chunks
    limit = _parallel_limit(tier_config, n_chunks)

    chunks: list[str] = []
    try:
        chunks = split_audio(audio_path, n_chunks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("split_audio failed: %s", exc)
        raise

    trans_coros = [
        transcribe_chunk(path, i) for i, path in enumerate(chunks)
    ]
    try:
        transcripts = await _gather_with_semaphore(trans_coros, limit)
    except Exception:
        for p in chunks:
            try:
                os.remove(p)
            except OSError:
                pass
        raise

    transcripts = sorted(transcripts, key=lambda x: x[0])
    full_transcript = " ".join(t[1] for t in transcripts)

    claim_coros = [
        extract_claims_chunk(t[1], t[0], precontext) for t in transcripts
    ]
    chunk_results = sorted(
        list(await _gather_with_semaphore(claim_coros, limit)),
        key=lambda r: r.chunk_index,
    )

    unified_claims = deduplicate_claims(chunk_results)
    unified_claims = await semantic_deduplicate_claims(unified_claims, precontext)
    canonical_entities = await coordinate_entities(chunk_results)

    for chunk_path in chunks:
        try:
            os.remove(chunk_path)
        except OSError:
            pass

    return {
        "transcript": full_transcript,
        "claims": unified_claims,
        "canonical_entities": [e.model_dump() for e in canonical_entities],
        "chunks_processed": strategy.n_chunks,
        "strategy": strategy.method,
    }
