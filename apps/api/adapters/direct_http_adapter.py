# direct_http_adapter.py
# Fetches direct URLs (images, PDFs, non-social media files).
# Used when source_url doesn't match a known social media domain.

import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .fetch_adapter import ChainOfCustodyBlock, FetchAdapter, FetchError, FetchResult

DIRECT_HTTP_ADAPTER_VERSION = "direct_http_v1"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB cap


class DirectHttpAdapter(FetchAdapter):
    def can_handle(self, source_url: str) -> bool:
        return source_url.startswith("http://") or source_url.startswith("https://")

    async def fetch(self, source_url: str) -> FetchResult:
        timestamp = datetime.now(timezone.utc).isoformat()

        server_ip = None
        try:
            hostname = urlparse(source_url).hostname
            if hostname:
                server_ip = socket.gethostbyname(hostname)
        except Exception:
            pass

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "Frame-Fetch/1.0 (+https://getframe.dev)"},
            ) as client:
                response = await client.get(source_url)
                response.raise_for_status()

                content_length = int(response.headers.get("content-length") or 0)
                if content_length > MAX_FILE_SIZE:
                    raise FetchError(
                        f"File too large: {content_length} bytes. Max is {MAX_FILE_SIZE}."
                    )

                file_bytes = response.content
                if len(file_bytes) > MAX_FILE_SIZE:
                    raise FetchError(f"Downloaded file exceeds {MAX_FILE_SIZE} byte limit.")

        except httpx.HTTPError as e:
            raise FetchError(f"HTTP fetch failed for {source_url}: {e!s}") from e

        sha256 = FetchResult.compute_hash(file_bytes)
        content_type = (
            response.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        )
        ext = _ext_from_content_type(content_type)

        chain = ChainOfCustodyBlock(
            retrieval_timestamp=timestamp,
            source_url=source_url,
            http_status=response.status_code,
            response_headers={k: v for k, v in response.headers.items()},
            tls_verified=source_url.startswith("https://"),
            server_ip=server_ip,
            fetch_adapter_version=DIRECT_HTTP_ADAPTER_VERSION,
        )

        return FetchResult(
            file_bytes=file_bytes,
            source_url=source_url,
            content_type=content_type,
            file_extension=ext,
            sha256_hash=sha256,
            chain_of_custody=chain,
            metadata={"final_url": str(response.url)},
        )


def _ext_from_content_type(ct: str) -> str:
    mapping = {
        "video/mp4": "mp4",
        "video/webm": "webm",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "application/pdf": "pdf",
    }
    return mapping.get(ct, "bin")
