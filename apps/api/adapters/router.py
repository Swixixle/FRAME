# router.py
# Selects the correct FetchAdapter for a given URL.

from .direct_http_adapter import DirectHttpAdapter
from .fetch_adapter import FetchAdapter
from .ytdlp_adapter import YtDlpAdapter


def get_adapter_for_url(source_url: str) -> FetchAdapter:
    """Return the best FetchAdapter for this URL."""
    ytdlp = YtDlpAdapter()
    if ytdlp.can_handle(source_url):
        return ytdlp
    return DirectHttpAdapter()
