"""Best-effort recording of finished searches into the history table."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from .state import _store


def search_fingerprint(
    query: str,
    sources: Optional[List[str]] = None,
    limit_per_source: int = 10,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    tech_only: bool = False,
    offset: int = 0,
    affiliation: Optional[str] = None,
    issn: Optional[str] = None,
    orcid: Optional[str] = None,
    doi: Optional[str] = None,
    sort: Optional[str] = None,
    order: str = "desc",
) -> str:
    """Hash everything that changes the result set.

    Source order is normalised because ``sources=a,b`` and ``sources=b,a``
    fetch the same papers; everything else is compared as-is.
    """
    payload = {
        "query": query,
        "sources": sorted(sources or []),
        "limit_per_source": limit_per_source,
        "year_from": year_from,
        "year_to": year_to,
        "tech_only": bool(tech_only),
        "offset": offset,
        "affiliation": affiliation,
        "issn": issn,
        "orcid": orcid,
        "doi": doi,
        "sort": sort,
        "order": order,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def _remember(
    query: Optional[str],
    sources: Optional[List[str]],
    filters: Dict[str, Any],
    payload: Any,
    fingerprint: Optional[str] = None,
) -> None:
    """Record a finished search in the history table, best effort.

    A fingerprint makes the write an upsert, so repeating an identical search
    refreshes one row instead of appending a duplicate.
    """
    store = _store()
    record = getattr(store, "record_search", None)
    if not callable(record):
        return
    kept = {name: value for name, value in filters.items() if value}
    results = (payload or {}).get("results") or []
    try:
        await record(
            query or "",
            author=None,
            sources=sources,
            filters=kept or None,
            result_count=len(results),
            results=results,
            fingerprint=fingerprint,
        )
    except Exception:
        return
