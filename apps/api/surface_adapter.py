"""
Layer 1 (Surface) — invokes `scripts/run-surface-layer.mjs` (Node + @frame/adapters),
or the podcast/video pipeline for media URLs (same transcription path as /v1/analyze-podcast).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from adapters_podcast import utterances_to_media_claims_dicts

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Inoculation baseline: fully traced Layer 1 for Slender Man / Victor Surge / Something Awful.
# Do not call the adapter for this route — benchmark for real traces.
SLENDERMAN_SURFACE_BASELINE: dict[str, Any] = {
    "what": (
        "Slender Man is a fictional Internet horror character created in June 2009 when "
        'Eric Knudsen (posting as Victor Surge) submitted two altered photographs to the '
        '"Create Paranormal Images" thread on the Something Awful forums. The '
        "character is not a verified real-world entity; it is documented as originating "
        "in that forum contest."
    ),
    "what_confidence_tier": "cross_corroborated",
    "who": [
        {"name": "Eric Knudsen (Victor Surge)", "confidence_tier": "official_primary"},
        {"name": "Something Awful", "confidence_tier": "official_secondary"},
    ],
    "when": {
        "earliest_appearance": (
            "June 2009 — first published appearance in the Something Awful forums thread "
            "\"Create Paranormal Images\" (Photoshop contest)."
        ),
        "source": (
            "Something Awful forums; documented attribution to Eric Knudsen (Victor Surge) "
            "as creator of the first Slender Man images."
        ),
        "confidence_tier": "cross_corroborated",
    },
    "source_url": None,
    "source_url_confidence_tier": None,
    "cultural_substrate": (
        "Late 2000s participatory web culture and Photoshop-driven horror "
        "memes on large forums, before the character spread into wider fiction."
    ),
    "absent_fields": [],
    "source_type": "text",
}


def _repo_root() -> Path:
    override = os.environ.get("FRAME_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def _sort_surface_who_in_result(result: dict[str, Any]) -> None:
    who = result.get("who")
    if isinstance(who, list) and who:
        result["who"] = sorted(
            who,
            key=lambda x: str((x or {}).get("name") or "").lower(),
        )
    sw = result.get("surface_who")
    if isinstance(sw, list) and sw:
        result["surface_who"] = sorted(
            sw,
            key=lambda x: str((x or {}).get("name") or "").lower(),
        )


_MEDIA_AUDIO_EXT = re.compile(r"\.(mp3|m4a|wav|ogg|opus|webm|flac)(\?|#|$)", re.I)
_PODCAST_RSS = re.compile(r"\.(rss|xml)(\?|#|$)", re.I)
_MEDIA_HOST = re.compile(
    r"youtube\.com|youtu\.be|m\.youtube\.com|music\.youtube\.com|"
    r"spotify\.com|soundcloud\.com|podcasts\.apple\.com|podcasters\.spotify\.com|"
    r"anchor\.fm|buzzsprout\.com|libsyn\.com|simplecast\.com|megaphone\.fm|"
    r"cloudfront\.net|\bcdn\.|/feeds/|traffic\.megaphone|dcs\.redcirc|\bpodcast\b",
    re.I,
)
_CDN_PATH = re.compile(r"/(audio|episode|episodes|media|podcast|podcasts|stream)/", re.I)


def detect_input_type(raw: str) -> str:
    """
    Mirror packages/adapters `detectInputType`: text | html_url | media_url.
    For non-http strings, returns text.
    """
    u = (raw or "").strip()
    if not u.startswith(("http://", "https://")):
        return "text"
    if _PODCAST_RSS.search(u):
        return "media_url"
    if _MEDIA_AUDIO_EXT.search(u):
        return "media_url"
    if _MEDIA_HOST.search(u):
        return "media_url"
    if _CDN_PATH.search(u) and _MEDIA_AUDIO_EXT.search(u):
        return "media_url"
    return "html_url"


def _format_ts(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(max(0.0, float(seconds)))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def map_podcast_to_surface(pod: dict[str, Any], source_url: str) -> dict[str, Any]:
    """Fold analyze-podcast-shaped payload into Layer 1 SurfaceResult + source_type + media_claims."""
    title = str(pod.get("podcastTitle") or pod.get("fileName") or "Media")[:500]
    claims: list[dict[str, Any]] = [
        dict(c) for c in (pod.get("extractedClaimObjects") or []) if isinstance(c, dict)
    ]
    full_text = str(pod.get("extractedText") or "")

    if claims:
        lead = [str(c.get("text") or "").strip() for c in claims[:4] if c.get("text")]
        what = (
            f'Transcribed media "{title}" surfaces checkable claims including: '
            + " ".join(lead[:3])
        )
        if len(what) > 1600:
            what = what[:1580] + "…"
    elif full_text.strip():
        what = (
            f'Transcribed media "{title}" ({len(full_text)} characters). '
            "No discrete factual claims were extracted from the transcript segment."
        )
    else:
        what = f'No transcript text was produced for "{title}".'

    speakers: set[str] = set()
    for c in claims:
        sp = str(c.get("speaker") or "").strip()
        if sp and sp.lower() != "unknown":
            speakers.add(sp)
        for ent in c.get("entities") or []:
            e = str(ent).strip()
            if e:
                speakers.add(e)

    ts_note = str(pod.get("timestamp") or "")
    when: dict[str, Any] = {
        "earliest_appearance": ts_note or "Unknown (pipeline does not resolve original publish time)",
        "source": source_url,
        "confidence_tier": "single_source",
    }

    absent: list[str] = []
    if not claims:
        absent.append("extracted_claims")
    absent.append("source_publication_date")

    transcript_obj = pod.get("transcript") if isinstance(pod.get("transcript"), dict) else {}
    raw_utterances = transcript_obj.get("utterances")
    utterance_mode = isinstance(raw_utterances, list) and len(raw_utterances) > 0

    media_claims: list[dict[str, Any]] = []
    if utterance_mode:
        ut_slice = [u for u in raw_utterances if isinstance(u, dict)][:80]
        media_claims = utterances_to_media_claims_dicts(ut_slice)
        for mc in media_claims:
            sp = str(mc.get("speaker") or "").strip()
            if sp and sp.lower() != "unknown":
                speakers.add(sp)
    else:
        for c in claims[:40]:
            risk = str(c.get("implication_risk") or "low").strip().lower()
            if risk not in ("low", "medium", "high"):
                risk = "low"
            try:
                ts0 = float(c.get("timestamp_start", 0))
            except (TypeError, ValueError):
                ts0 = 0.0
            try:
                ts1 = float(c.get("timestamp_end", ts0))
            except (TypeError, ValueError):
                ts1 = ts0
            media_claims.append(
                {
                    "timestamp_label": _format_ts(ts0),
                    "timestamp_start": ts0,
                    "timestamp_end": ts1,
                    "speaker": str(c.get("speaker") or "unknown"),
                    "text": str(c.get("text") or "")[:2000],
                    "confidence_tier": risk,
                }
            )

    who: list[dict[str, str]] = [{"name": s, "confidence_tier": "single_source"} for s in sorted(speakers)]
    if not who:
        who = [{"name": f'Source: {title[:120]}', "confidence_tier": "single_source"}]

    out: dict[str, Any] = {
        "what": what,
        "cultural_substrate": None,
        "what_confidence_tier": "single_source",
        "who": who,
        "when": when,
        "source_url": source_url,
        "source_url_confidence_tier": "official_secondary",
        "absent_fields": absent,
        "source_type": "media",
        "media_claims": media_claims,
        "podcast_note": pod.get("note"),
    }
    _sort_surface_who_in_result(out)
    return out


def run_podcast_layer(url: str) -> dict[str, Any]:
    """
    Same transcription + claim-extraction path as /v1/analyze-podcast (adapters_podcast),
    without importing `main` (avoids loading db/redis on CLI smoke).
    Skips async source verification / adapter routing present on the HTTP route.
    """
    from datetime import datetime, timezone

    from adapters_podcast import (
        PODCAST_MAX_SECONDS,
        download_audio,
        extract_speaker_claims,
        transcribe_audio,
        trim_audio_max,
    )

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    u = (url or "").strip()
    dl = download_audio(u)
    audio_path = dl["path"]
    title = str(dl.get("title") or "podcast")[:500]
    source_url = str(dl.get("source_url") or u)
    trimmed_path, was_trimmed = trim_audio_max(audio_path, PODCAST_MAX_SECONDS)
    file_size = Path(trimmed_path).stat().st_size

    transcript = transcribe_audio(trimmed_path)
    claim_extract_error: str | None = None
    try:
        raw_claims = extract_speaker_claims(transcript, title)
    except Exception as exc:  # noqa: BLE001
        raw_claims = []
        claim_extract_error = str(exc)[:300]

    extracted_claim_objects: list[dict[str, Any]] = [dict(c) for c in raw_claims]
    note_parts = [
        "v1: First "
        + str(PODCAST_MAX_SECONDS // 60)
        + " minutes only — longer audio is truncated.",
    ]
    if was_trimmed:
        note_parts.append("This file was trimmed to the cap.")
    if claim_extract_error:
        note_parts.append(f"Claim extraction issue: {claim_extract_error}")
    note = " ".join(note_parts)

    pod: dict[str, Any] = {
        "fileHash": None,
        "fileName": title[:240],
        "fileSize": file_size,
        "contentType": "audio/mpeg",
        "timestamp": timestamp,
        "extractedText": transcript.get("full_text"),
        "extractedClaimObjects": extracted_claim_objects,
        "podcastTitle": title,
        "transcript": transcript,
        "note": note,
        "sourceUrl": source_url,
    }
    return map_podcast_to_surface(pod, source_url)


def _run_node_surface(sub: dict[str, Any]) -> dict[str, Any]:
    """Run the TypeScript surface adapter via Node (requires `npm run build` and ANTHROPIC_API_KEY)."""
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise RuntimeError("ANTHROPIC_API_KEY is required for surface extraction")

    root = _repo_root()
    script = root / "scripts" / "run-surface-layer.mjs"
    if not script.is_file():
        raise RuntimeError(f"Surface script missing: {script}")

    proc = subprocess.run(
        ["node", str(script)],
        input=json.dumps(sub),
        text=True,
        capture_output=True,
        cwd=str(root),
        env={**os.environ},
        timeout=120,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        for line in err.splitlines():
            t = line.strip()
            if t.startswith("Error:") and "Anthropic surface:" in t:
                t = t.removeprefix("Error:").strip()
                raise RuntimeError(t[:2000])
        raise RuntimeError((err[:1500] if err else "surface adapter failed"))
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError("surface adapter returned empty stdout")
    return json.loads(out)


def run_surface_layer(body: dict[str, Any]) -> dict[str, Any]:
    """
    Layer 1: plain text / HTML URL via Node surface adapter; media URL via podcast transcription + mapping.
    """
    url = (body.get("url") or "").strip()
    narrative = (body.get("narrative") or "").strip()

    candidate_url = url
    if not candidate_url and narrative.startswith(("http://", "https://")):
        candidate_url = narrative.strip()

    if candidate_url:
        kind = detect_input_type(candidate_url)
        if kind == "media_url":
            out = run_podcast_layer(candidate_url)
        else:
            out = _run_node_surface({"url": candidate_url})
        _sort_surface_who_in_result(out)
        return out

    if not narrative:
        raise RuntimeError("Provide narrative or url")

    out = _run_node_surface({"narrative": narrative})
    _sort_surface_who_in_result(out)
    return out
