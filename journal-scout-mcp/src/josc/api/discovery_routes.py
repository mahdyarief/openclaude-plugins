"""Bibliometrics and GraphML export routes.

These sit next to :mod:`search_routes` because they share the same cache keys
and the same aggregator calls, but they return renderable artefacts (CSV, plain
text, XML) rather than raw JSON.
"""

from __future__ import annotations

from typing import Any, Dict

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from .. import aggregator
from ..exporters import format_metrics_csv, format_search_report
from .responses import _error
from .search_routes import network
from .state import _cached, _flag, _int, _providers, _sources


async def _metrics_payload(request: Request) -> Dict[str, Any]:
    author = (request.query_params.get("author") or "").strip() or None
    query = (request.query_params.get("query") or "").strip() or None
    if not (author or query):
        raise ValueError("Provide either 'author' or 'query'.")
    limit_per_source = _int(request, "limit_per_source", 50)
    year_from = _int(request, "year_from")
    year_to = _int(request, "year_to")
    sources = _sources(request)
    mode = request.query_params.get("mode") or "basic"
    key = ("metrics", author, query, limit_per_source, year_from, year_to, sources, mode)
    offline = _flag(request, "offline")
    return await _cached(
        key,
        lambda: aggregator.compute_metrics(
            _providers(),
            author=author,
            query=query,
            limit_per_source=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            sources=sources,
            mode=mode,
        ),
        offline=offline,
    )


async def metrics(request: Request) -> JSONResponse:
    try:
        payload = await _metrics_payload(request)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def metrics_export(request: Request) -> Response:
    try:
        payload = await _metrics_payload(request)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return PlainTextResponse(format_metrics_csv(payload), media_type="text/csv")


async def metrics_report(request: Request) -> Response:
    try:
        payload = await _metrics_payload(request)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    mode = request.query_params.get("mode") or "basic"
    return PlainTextResponse(
        format_search_report(payload, mode), media_type="text/plain; charset=utf-8"
    )


async def graphml_export(request: Request) -> Response:
    return await network(request)
