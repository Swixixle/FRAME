"""Citizens United v. FEC — documented vote alignment (U.S. Reports + CourtListener)."""

from __future__ import annotations

import logging
import re
from typing import Any

_LOG = logging.getLogger(__name__)

_CITIZENS_UNION_OPINION_URL = (
    "https://www.courtlistener.com/opinion/1741/citizens-united-v-federal-election-commission/"
)
_SOURCE_NOTE = "U.S. Reports, 558 U.S. 310; CourtListener opinion/1741"

_CU_MAJORITY: list[dict[str, Any]] = [
    {"name": "John G. Roberts Jr.", "role": "Chief Justice", "vote": "majority", "joined_court": 2005},
    {"name": "Antonin Scalia", "role": "Associate Justice", "vote": "majority", "joined_court": 1986},
    {
        "name": "Anthony Kennedy",
        "role": "Associate Justice",
        "vote": "majority",
        "wrote_opinion": True,
        "joined_court": 1988,
    },
    {"name": "Clarence Thomas", "role": "Associate Justice", "vote": "majority", "joined_court": 1991},
    {"name": "Samuel Alito Jr.", "role": "Associate Justice", "vote": "majority", "joined_court": 2006},
]

_CU_DISSENT: list[dict[str, Any]] = [
    {
        "name": "John Paul Stevens",
        "role": "Associate Justice",
        "vote": "dissent",
        "wrote_dissent": True,
        "joined_court": 1975,
    },
    {"name": "Ruth Bader Ginsburg", "role": "Associate Justice", "vote": "dissent", "joined_court": 1993},
    {"name": "Stephen Breyer", "role": "Associate Justice", "vote": "dissent", "joined_court": 1994},
    {"name": "Sonia Sotomayor", "role": "Associate Justice", "vote": "dissent", "joined_court": 2009},
]


def get_citizens_united_justices() -> dict[str, list[dict[str, Any]]]:
    return {"majority": [dict(j) for j in _CU_MAJORITY], "dissent": [dict(j) for j in _CU_DISSENT]}


def _judicial_network_query_match(query: str) -> bool:
    q = (query or "").lower()
    if any(
        s in q
        for s in (
            "citizens united",
            "campaign finance",
            "first amendment",
            "corporate speech",
            "super pac",
        )
    ):
        return True
    return bool(re.search(r"(?<![a-z])pac(?![a-z])", q))


async def build_judicial_network(query: str) -> dict[str, Any]:
    try:
        if not _judicial_network_query_match(query):
            return {}
        roster = get_citizens_united_justices()
        return {
            "decision": "Citizens United v. Federal Election Commission, 558 U.S. 310 (2010)",
            "vote_tally": "5-4",
            "opinion_url": _CITIZENS_UNION_OPINION_URL,
            "majority": roster["majority"],
            "dissent": roster["dissent"],
            "source_type": "judicial_network",
            "source": _SOURCE_NOTE,
        }
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("build_judicial_network failed: %s", exc)
        return {}

