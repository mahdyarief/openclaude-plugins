"""Archive routes: paper export, merge, search archives and workspace archives.

Every archive route degrades to a 400 with a readable message when the
persistent store is not configured, because history is an optional feature.
"""

from __future__ import annotations

from typing import Any, List

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from ..exporters import format_papers
from ..importers import detect_format, parse_import
from ..merge import merge_papers
from ..models import Paper
from .responses import _error
from .state import _int, _providers, _store

_PAPER_FIELDS = frozenset(Paper.__dataclass_fields__)


def _papers_from_body(papers: Any) -> List[Paper]:
    if not isinstance(papers, list):
        raise ValueError("'papers' must be an array of paper objects.")
    out: List[Paper] = []
    for item in papers:
        if not isinstance(item, dict):
            raise ValueError("Each entry in 'papers' must be an object.")
        # Ignore unknown keys rather than raising: the UI round-trips whatever
        # the search returned, which may carry provider-specific extras.
        out.append(Paper(**{k: v for k, v in item.items() if k in _PAPER_FIELDS}))
    return out


async def export(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 - malformed JSON is a client error
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    papers = body.get("papers")
    fmt = body.get("format")
    if not isinstance(papers, list):
        return _error(ValueError("'papers' must be an array of paper objects."))
    if not isinstance(fmt, str) or not fmt.strip():
        return _error(ValueError("'format' must be a non-empty string."))
    try:
        content = format_papers(papers, fmt)
    except ValueError as exc:
        return _error(exc)
    return PlainTextResponse(content)


async def merge(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    try:
        papers = _papers_from_body(body.get("papers"))
    except ValueError as exc:
        return _error(exc)
    merged = merge_papers(papers)
    return JSONResponse(
        {
            "results": [paper.to_dict() for paper in merged],
            "input_count": len(papers),
            "merged_count": len(merged),
        }
    )


async def search_export(request: Request) -> Response:
    store = _store()
    getter = getattr(store, "get_search", None)
    if not callable(getter):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        row = await getter(request.path_params["search_id"])
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if row is None:
        return JSONResponse({"error": "Search not found."}, status_code=404)
    return JSONResponse(
        {
            "format": "josc-search-archive",
            "version": 1,
            "query": row.get("query"),
            "author": row.get("author"),
            "sources": row.get("sources"),
            "filters": row.get("filters"),
            "created_at": row.get("created_at"),
            "results": row.get("results") or [],
        }
    )


async def search_import(request: Request) -> JSONResponse:
    store = _store()
    importer = getattr(store, "import_search", None)
    if not callable(importer):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    results = body.get("results")
    if not isinstance(results, list):
        return _error(ValueError("'results' must be an array of paper objects."))
    query = body.get("query")
    if not isinstance(query, str):
        return _error(ValueError("'query' must be a string."))
    try:
        search_id = await importer(
            body,
            query=query,
            author=body.get("author"),
            sources=body.get("sources"),
            filters=body.get("filters"),
            results=results,
            result_count=len(results),
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if search_id is None:
        return _error(ValueError("Could not persist the imported archive."))
    return JSONResponse({"id": search_id, "result_count": len(results)})


async def workspace_export(request: Request) -> JSONResponse:
    """Export every archived search as one portable workspace archive."""
    store = _store()
    exporter = getattr(store, "export_workspace", None)
    if not callable(exporter):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        rows = await exporter(limit=_int(request, "limit", 200) or 200)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(
        {
            "format": "josc-workspace-archive",
            "version": 1,
            "count": len(rows),
            "searches": rows,
        }
    )


async def workspace_import(request: Request) -> JSONResponse:
    """Import a workspace archive produced by ``GET /api/searches/export``."""
    store = _store()
    importer = getattr(store, "import_workspace", None)
    if not callable(importer):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    if not isinstance(body.get("searches"), list):
        return _error(ValueError("'searches' must be an array."))
    try:
        ids = await importer(body)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse({"ids": ids, "count": len(ids)})


async def import_external(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    content = body.get("content")
    if not isinstance(content, str):
        return _error(ValueError("'content' must be a string."))
    fmt = body.get("format")
    filename = body.get("filename")
    try:
        resolved = detect_format(filename, content) if not fmt else fmt
        papers = parse_import(content, fmt)
    except ValueError as exc:
        return _error(exc)
    return JSONResponse({"format": resolved, "count": len(papers), "papers": papers})


async def quota(request: Request) -> JSONResponse:
    from ..quota import quota_report

    return JSONResponse(quota_report(_providers()))
