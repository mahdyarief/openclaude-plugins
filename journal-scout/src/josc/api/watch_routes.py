"""REST handlers for saved-search watches.

The check itself lives in the MCP tool, because only that path has a search
runner. REST can create, list, delete and serve the last persisted result set.
"""

import json
from typing import Any

from starlette.responses import JSONResponse, Response

from ..watch_diff import render_rss
from .responses import _error


def _watches(request: Any):
    return request.app.state.watches


async def watches_list_create(request: Any):
    store = _watches(request)
    if store is None:
        return _error("Persistent watch store is not configured.", 503)
    if request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return _error("invalid JSON body", 400)
        query = (body.get("query") or "").strip()
        if not query:
            return _error("query is required", 400)
        watch_id = await store.create(
            query,
            author=body.get("author"),
            sources=body.get("sources"),
            filters=body.get("filters"),
        )
        return JSONResponse({"id": watch_id}, status_code=201)
    return JSONResponse({"watches": await store.list()})


async def watch_delete(request: Any):
    store = _watches(request)
    if store is None:
        return _error("Persistent watch store is not configured.", 503)
    deleted = await store.delete(request.path_params["watch_id"])
    if not deleted:
        return _error("watch not found", 404)
    return JSONResponse({"deleted": True})


async def watch_feed(request: Any):
    store = _watches(request)
    if store is None:
        return _error("Persistent watch store is not configured.", 503)
    watch = await store.get(request.path_params["watch_id"])
    if watch is None:
        return _error("watch not found", 404)
    body = render_rss(
        f"Watch: {watch['query']}",
        f"/api/watches/{watch['id']}/feed",
        watch.get("last_results") or [],
    )
    return Response(body, media_type="application/rss+xml")
