"""
Podcast / video adapter: download audio, Whisper transcription, Claude claim extraction.

Caps: first 30 minutes of audio only (v1 — Render timeouts).
Requires: yt-dlp, ffmpeg (for trim), openai-whisper, ANTHROPIC_API_KEY for claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

# Max audio processed (seconds) — v1 cap for serverless timeouts
PODCAST_MAX_SECONDS = int(os.environ.get("FRAME_PODCAST_MAX_SECONDS", str(30 * 60)))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def acoustic_fingerprint(audio_path: str) -> str:
    """
    SHA-256 of decoded PCM from the first ~30s of audio (ffmpeg).
    Falls back to first 512KiB of file bytes if ffmpeg is unavailable.
    """
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                audio_path,
                "-t",
                "30",
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "pipe:1",
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            return hashlib.sha256(proc.stdout).hexdigest()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    with open(audio_path, "rb") as f:
        chunk = f.read(512_000)
    return hashlib.sha256(chunk).hexdigest()


def download_audio(url: str) -> dict[str, Any]:
    """
    Download best audio-only stream with yt-dlp to /tmp/frame_podcast/{hash}.<ext>.
    Returns path, title, duration (if known), source_url, downloaded_at.
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must be http(s)")

    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    out_dir = Path(os.environ.get("FRAME_PODCAST_TMP", "/tmp/frame_podcast"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tpl = str(out_dir / f"{h}.%(ext)s")

    title = "podcast"
    duration: float | None = None
    meta = subprocess.run(
        ["yt-dlp", "--no-playlist", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if meta.returncode == 0 and meta.stdout:
        try:
            line = meta.stdout.strip().splitlines()[0]
            j = json.loads(line)
            title = str(j.get("title") or title)[:500]
            d = j.get("duration")
            if d is not None:
                duration = float(d)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    proc = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--max-downloads",
            "1",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "5",
            "-o",
            out_tpl,
            url,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]
        raise RuntimeError(f"yt-dlp failed: {err}")

    matches = sorted(out_dir.glob(f"{h}.*"))
    filepath = ""
    for p in matches:
        if p.is_file() and p.suffix.lower() in (
            ".mp3",
            ".m4a",
            ".opus",
            ".webm",
            ".ogg",
            ".wav",
        ):
            filepath = str(p)
            break
    if not filepath and matches:
        filepath = str(matches[0])
    if not filepath or not Path(filepath).is_file():
        raise RuntimeError("yt-dlp did not produce an audio file")

    return {
        "path": filepath,
        "title": title,
        "duration": duration,
        "source_url": url,
        "downloaded_at": _now_iso(),
    }


def trim_audio_max(input_path: str, max_seconds: int = PODCAST_MAX_SECONDS) -> tuple[str, bool]:
    """
    If longer than max_seconds, write trimmed copy next to input. Returns (path_to_use, was_trimmed).
    """
    out = str(Path(input_path).with_suffix("")) + ".frame30m.mp3"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            input_path,
            "-t",
            str(max_seconds),
            "-c",
            "copy",
            out,
        ],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode == 0 and Path(out).is_file():
        return out, True
    # Fallback: use original (Whisper still processes but may timeout on huge files)
    return input_path, False


_whisper_model: Any = None


def _get_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        import whisper  # openai-whisper

        _whisper_model = whisper.load_model(os.environ.get("FRAME_WHISPER_MODEL", "base"))
    return _whisper_model


def transcribe_audio(path: str) -> dict[str, Any]:
    """Run local Whisper (base). Returns segments, full_text, duration."""
    model = _get_whisper_model()
    result = model.transcribe(path, fp16=False, verbose=False)
    segments: list[dict[str, Any]] = []
    for s in result.get("segments") or []:
        segments.append(
            {
                "start": float(s.get("start", 0)),
                "end": float(s.get("end", 0)),
                "text": str(s.get("text", "")).strip(),
            }
        )
    full_text = str(result.get("text") or "").strip()
    dur = float(result.get("duration") or 0)
    if not dur and segments:
        dur = float(segments[-1].get("end") or 0)
    return {
        "segments": segments,
        "full_text": full_text,
        "duration": dur,
    }


def extract_speaker_claims(transcript: dict[str, Any], title: str) -> list[dict[str, Any]]:
    """
    Call Claude to extract verifiable factual claims with timestamps and entities.
    Returns list of dicts: text, type, entities, timestamp_start, timestamp_end, speaker, primary_sources.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY required for claim extraction")

    import anthropic as ant

    full_text = transcript.get("full_text") or ""
    segments = transcript.get("segments") or []
    # Bound prompt size (~24k chars)
    if len(full_text) > 24000:
        full_text = full_text[:24000] + "\n\n[… transcript truncated for claim extraction …]"
    seg_preview = json.dumps(segments[:400], ensure_ascii=False)[:12000]

    client = ant.Anthropic(api_key=key)
    prompt = f"""Episode / clip title: {title}

You are analyzing a podcast/video transcript. Return JSON only — no markdown.

Full transcript text:
{full_text}

Segment timestamps (reference for alignment):
{seg_preview}

Task:
- Identify distinct speakers when possible (host, guest, or "unknown").
- Extract only **verifiable factual claims** — not opinions, predictions, or hedged speculation.
- For each claim assign: type (one of: financial, government_action, biographical, lobbying, health, statistical, legal, corporate, election, general).
- Named entities per claim (people, orgs, agencies).
- timestamp_start and timestamp_end in **seconds** (float) covering when the claim is stated (infer from transcript).
- Up to 2 primary source URLs per claim (real government/database URLs when possible).

Return exactly this JSON shape:
{{
  "claims": [
    {{
      "text": "the specific factual assertion",
      "type": "government_action",
      "entities": ["Name One", "Agency"],
      "timestamp_start": 74.2,
      "timestamp_end": 82.0,
      "speaker": "guest",
      "primary_sources": [
        {{ "label": "short name", "url": "https://...", "type": "government" }}
      ]
    }}
  ]
}}

If no factual claims: {{"claims": []}}.
"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    block = msg.content[0]
    raw = getattr(block, "text", str(block)).strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    data = json.loads(raw)
    claims = data.get("claims") or []
    out: list[dict[str, Any]] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        text = str(c.get("text") or "").strip()
        if not text:
            continue
        ctype = str(c.get("type") or "general").strip() or "general"
        entities = c.get("entities") if isinstance(c.get("entities"), list) else []
        entities = [str(e).strip() for e in entities if str(e).strip()]
        try:
            ts = float(c.get("timestamp_start", 0))
        except (TypeError, ValueError):
            ts = 0.0
        try:
            te = float(c.get("timestamp_end", ts))
        except (TypeError, ValueError):
            te = ts
        speaker = str(c.get("speaker") or "unknown").strip() or "unknown"
        ps = c.get("primary_sources") if isinstance(c.get("primary_sources"), list) else []
        clean_ps: list[dict[str, Any]] = []
        for p in ps[:3]:
            if not isinstance(p, dict):
                continue
            u = str(p.get("url") or "").strip()
            if not u.startswith("http"):
                continue
            clean_ps.append(
                {
                    "label": str(p.get("label") or "source")[:200],
                    "url": u,
                    "type": str(p.get("type") or "database")[:80],
                }
            )
        out.append(
            {
                "text": text[:2000],
                "type": ctype,
                "entities": entities[:20],
                "timestamp_start": ts,
                "timestamp_end": te,
                "speaker": speaker[:80],
                "primary_sources": clean_ps,
            }
        )
    return out[:15]


def save_uploaded_audio(data: bytes, filename: str) -> dict[str, Any]:
    """Write upload to temp path; return same shape as download_audio (no duration from yt-dlp)."""
    ext = Path(filename or "audio").suffix.lower() or ".mp3"
    if ext not in (".mp3", ".m4a", ".wav", ".ogg", ".webm", ".opus", ".flac"):
        ext = ".mp3"
    h = hashlib.sha256(data).hexdigest()[:16]
    out_dir = Path(os.environ.get("FRAME_PODCAST_TMP", "/tmp/frame_podcast"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = str(out_dir / f"upload-{h}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return {
        "path": path,
        "title": Path(filename).stem or "upload",
        "duration": None,
        "source_url": "upload://local",
        "downloaded_at": _now_iso(),
    }
