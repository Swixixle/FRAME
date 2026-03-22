# fetch_adapter.py
# Interface contract: URL in → file bytes + metadata + chain_of_custody out.
# Platform changes replace the implementation, not this interface.
# Current implementations: YtDlpAdapter, DirectHttpAdapter

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ChainOfCustodyBlock:
    retrieval_timestamp: str
    source_url: str
    http_status: Optional[int]
    response_headers: dict[str, Any]
    tls_verified: bool
    server_ip: Optional[str]
    fetch_adapter_version: str  # e.g. "ytdlp_v1" or "direct_http_v1"


@dataclass
class FetchResult:
    file_bytes: bytes
    source_url: str
    content_type: str
    file_extension: str
    sha256_hash: str
    chain_of_custody: ChainOfCustodyBlock
    temp_file_path: Optional[str] = None  # set if written to disk
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def compute_hash(cls, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


class AdapterUnavailableError(Exception):
    """Raised when a required system dependency is not installed."""

    pass


class FetchError(Exception):
    """Raised when fetch fails for a recoverable reason (platform blocked, etc.)"""

    pass


class FetchAdapter(ABC):
    @abstractmethod
    async def fetch(self, source_url: str) -> FetchResult:
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, source_url: str) -> bool:
        """Return True if this adapter can handle the given URL."""
        raise NotImplementedError
