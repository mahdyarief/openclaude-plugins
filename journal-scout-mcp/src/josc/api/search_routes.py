"""Discovery routes: search, author search, single paper and citation edges."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from .. import aggregator
from ..providers import provider_names
from . import history
from .responses import _cache_stats, _error, _store_stats
from .state import (
    _cached,
    _flag,
    _identifier,
    _int,
    _providers,
    _sources,
    _store,
    _text,
)


async def searches(request: Request) -> JSONResponse:
    """Return recent searches, newest first."""
    store = _store()
    lister = getattr(store, "list_searches", None)
    if not callable(lister):
        return JSONResponse({"searches": [], "persistent": False})
    try:
        rows = await lister(limit=_int(request, "limit", 20) or 20)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse({"searches": rows, "persistent": True})


async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "sources": provider_names(),
            "cache": _cache_stats(),
            "store": await _store_stats(),
            "capabilities": {
                p.name: {
                    "search": getattr(p, "supports_search", False),
                    "citations": getattr(p, "supports_citations", False),
                    "references": getattr(p, "supports_references", False),
                    "related": getattr(p, "supports_related", False),
                    "author_search": getattr(p, "supports_author_search", False),
                    "tech_only": getattr(p, "supports_tech_only", False),
                    "filters": sorted(getattr(p, "supports_filters", ()) or ()),
                }
                for p in _providers()
            },
        }
    )


def _conditions(request: Request) -> Optional[List[Dict[str, Any]]]:
    raw = (request.query_params.get("conditions") or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"'conditions' must be a JSON array: {exc.msg}") from exc
    if not isinstance(parsed, list):
        raise ValueError("'conditions' must be a JSON array.")
    return parsed


async def search(request: Request) -> JSONResponse:
    query = (request.query_params.get("query") or "").strip()
    try:
        conditions = _conditions(request)
    except ValueError as exc:
        return _error(exc)
    if not query and not conditions:
        return _error(
            ValueError("Provide either 'query' or a non-empty 'conditions' array.")
        )
    limit_per_source = _int(request, "limit_per_source", 10)
    year_from = _int(request, "year_from")
    year_to = _int(request, "year_to")
    tech_only = request.query_params.get("tech_only", "").lower() in ("1", "true", "yes")
    sources = _sources(request)
    offset = _int(request, "offset", 0)
    author = _text(request, "author")
    venue = _text(request, "venue")
    affiliation = _text(request, "affiliation")
    issn = _text(request, "issn")
    orcid = _text(request, "orcid")
    doi = _text(request, "doi")
    sort = _text(request, "sort")
    order = _text(request, "order") or "desc"
    topic = _text(request, "topic")
    key = ("search", query, conditions, limit_per_source, year_from, year_to,
           tech_only, sources, offset, author, venue, affiliation, issn, orcid,
           doi, sort, order, topic)
    offline = _flag(request, "offline")
    try:
        payload = await _cached(
            key,
            lambda: aggregator.search_all(
                _providers(),
                query,
                limit_per_source=limit_per_source,
                year_from=year_from,
                year_to=year_to,
                tech_only=tech_only,
                sources=sources,
                offset=offset,
                author=author,
                venue=venue,
                affiliation=affiliation,
                issn=issn,
                orcid=orcid,
                doi=doi,
                sort=sort,
                order=order,
                topic=topic,
                conditions=conditions,
            ),
            offline=offline,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a JSON error to the UI
        return _error(exc)
    if not offline:
        filters = {"author": author, "venue": venue,
                   "affiliation": affiliation, "issn": issn,
                   "orcid": orcid, "doi": doi, "topic": topic}
        fingerprint = history.search_fingerprint(
            query=query,
            sources=sources,
            limit_per_source=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            tech_only=tech_only,
            offset=offset,
            author=author,
            venue=venue,
            affiliation=affiliation,
            issn=issn,
            orcid=orcid,
            doi=doi,
            sort=sort,
            order=order,
            topic=topic,
            conditions=conditions,
        )
        await history._remember(
            query=query,
            sources=sources,
            filters=filters,
            payload=payload,
            fingerprint=fingerprint,
        )
    return JSONResponse(payload)


async def search_author(request: Request) -> JSONResponse:
    author = (request.query_params.get("author") or "").strip()
    if not author:
        return _error(ValueError("Missing required query parameter 'author'."))
    limit_per_source = _int(request, "limit_per_source", 10)
    year_from = _int(request, "year_from")
    year_to = _int(request, "year_to")
    sources = _sources(request)
    offset = _int(request, "offset", 0)
    key = ("search_author", author, limit_per_source, year_from, year_to, sources, offset)
    offline = _flag(request, "offline")
    try:
        payload = await _cached(
            key,
            lambda: aggregator.search_author(
                _providers(),
                author,
                limit_per_source=limit_per_source,
                year_from=year_from,
                year_to=year_to,
                sources=sources,
                offset=offset,
            ),
            offline=offline,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def paper(request: Request) -> JSONResponse:
    try:
        payload = await aggregator.get_paper(
            _providers(), _identifier(request), sources=_sources(request)
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def citations(request: Request) -> JSONResponse:
    identifier = _identifier(request)
    try:
        payload = await aggregator.get_citations(
            _providers(),
            identifier,
            limit=_int(request, "limit", 20),
            sources=_sources(request),
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if _flag(request, "save"):
        await history._remember(
            query=f"citations:{identifier}",
            sources=None,
            filters={},
            payload=payload,
        )
    return JSONResponse(payload)


async def references(request: Request) -> JSONResponse:
    try:
        payload = await aggregator.get_references(
            _providers(),
            _identifier(request),
            limit=_int(request, "limit", 20),
            sources=_sources(request),
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def related(request: Request) -> JSONResponse:
    try:
        payload = await aggregator.get_related(
            _providers(),
            _identifier(request),
            limit=_int(request, "limit", 20),
            sources=_sources(request),
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def network(request: Request) -> Response:
    identifier = _identifier(request)
    limit = _int(request, "limit", 20)
    citing_limit = _int(request, "citing_limit", 10)
    max_nodes = _int(request, "max_nodes", 200)
    reference_limit = _int(request, "reference_limit", 10)
    graph_format = request.query_params.get("format", "json")
    key = (
        "network",
        identifier,
        limit,
        citing_limit,
        max_nodes,
        reference_limit,
        graph_format,
    )
    offline = _flag(request, "offline")
    try:
        payload = await _cached(
            key,
            lambda: aggregator.build_citation_network(
                _providers(),
                identifier,
                limit=limit,
                citing_limit=citing_limit,
                max_nodes=max_nodes,
                graph_format=graph_format,
                reference_limit=reference_limit,
            ),
            offline=offline,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)

    if payload.get("format") == "graphml":
        return PlainTextResponse(
            payload["graphml"],
            media_type="application/xml",
            headers={
                "Content-Disposition": 'attachment; filename="citation-network.graphml"'
            },
        )
    return JSONResponse(payload)
