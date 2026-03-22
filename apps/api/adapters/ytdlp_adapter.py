# ytdlp_adapter.py
# Fetches social media content via yt-dlp.
# Handles: Instagram, TikTok, YouTube, Facebook, Twitter/X, ~1000 others.
# yt-dlp is a moving target — platform cat-and-mouse is ongoing.
# Pin version in requirements.txt. Check for updates monthly.

import asyncio
import os
import tempfile
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from .fetch_adapter import (
    AdapterUnavailableError,
    ChainOfCustodyBlock,
    FetchAdapter,
    FetchError,
    FetchResult,
)

YTDLP_ADAPTER_VERSION = "ytdlp_v1"

SOCIAL_DOMAINS = [
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "fb.watch",
    "twitter.com",
    "x.com",
    "reddit.com",
    "twitch.tv",
    "vimeo.com",
]


class YtDlpAdapter(FetchAdapter):
    def can_handle(self, source_url: str) -> bool:
        low = source_url.lower()
        return any(domain in low for domain in SOCIAL_DOMAINS)

    async def fetch(self, source_url: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_sync, source_url)

    def _fetch_sync(self, source_url: str) -> FetchResult:
        try:
            import yt_dlp
        except ImportError:
            raise AdapterUnavailableError(
                "yt-dlp is not installed. Add 'yt-dlp' to requirements.txt "
                "and redeploy. Required for social media URL fetch."
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        temp_dir = tempfile.mkdtemp(prefix="frame_fetch_")
        output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "format": "best[filesize<100M]/best",  # cap at 100MB
            "socket_timeout": 30,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                raw_info = ydl.extract_info(source_url, download=True)
        except Exception as e:
            raise FetchError(f"yt-dlp fetch failed for {source_url}: {e!s}") from e

        info: dict = raw_info if isinstance(raw_info, dict) else {}

        downloaded_file = None
        for fname in sorted(os.listdir(temp_dir)):
            fp = os.path.join(temp_dir, fname)
            if os.path.isfile(fp):
                downloaded_file = fp
                break

        if not downloaded_file or not os.path.exists(downloaded_file):
            raise FetchError(f"yt-dlp completed but no file found in {temp_dir}")

        with open(downloaded_file, "rb") as f:
            file_bytes = f.read()

        sha256 = FetchResult.compute_hash(file_bytes)
        ext = os.path.splitext(downloaded_file)[1].lstrip(".") or "bin"

        server_ip = None
        try:
            hostname = urlparse(source_url).hostname
            if hostname:
                server_ip = socket.gethostbyname(hostname)
        except Exception:
            pass

        chain = ChainOfCustodyBlock(
            retrieval_timestamp=timestamp,
            source_url=source_url,
            http_status=200,  # yt-dlp succeeded — implied 200
            response_headers={
                "x-frame-note": "Headers captured via yt-dlp; platform headers not directly accessible"
            },
            tls_verified=source_url.startswith("https://"),
            server_ip=server_ip,
            fetch_adapter_version=YTDLP_ADAPTER_VERSION,
        )

        return FetchResult(
            file_bytes=file_bytes,
            source_url=source_url,
            content_type=_guess_content_type(ext),
            file_extension=ext,
            sha256_hash=sha256,
            chain_of_custody=chain,
            temp_file_path=downloaded_file,
            metadata={
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "platform": info.get("extractor"),
                "temp_fetch_dir": temp_dir,
            },
        )


def _guess_content_type(ext: str) -> str:
    mapping = {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mapping.get(ext.lower(), "application/octet-stream")
