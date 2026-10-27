"""Starlette application assembly for josc-web.

Thin wrapper around :mod:`josc.aggregator`. Every route maps to one aggregator
call so the browser app and the MCP server stay on the same code path.
Identifiers are passed as query parameters rather than path segments because
DOIs contain slashes.

Run with::

    uv run josc-web               # or: uvicorn josc.api:app --port 8793
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .recognize_routes import identify
from .library_routes import (
    export,
    import_external,
    merge,
    quota,
    search_export,
    search_import,
    workspace_export,
    workspace_import,
)
from .cache_routes import (
    cache_clear,
    cache_info,
    search_delete,
    search_duplicate,
    search_replay,
    search_split,
)
from .discovery_routes import (
    graphml_export,
    metrics,
    metrics_export,
    metrics_report,
)
from .search_routes import (
    citations,
    health,
    network,
    paper,
    references,
    related,
    search,
    search_author,
    searches,
)
from .watch_routes import watch_delete, watch_feed, watches_list_create
from ..watches import WatchStore
from .state import _store, setup_state, teardown_state

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


class SPAStaticFiles(StaticFiles):
    """Serve ``index.html`` for client-side routes.

    TanStack Router keeps every page under one HTML shell, so ``/history`` is
    not a file in ``web/dist``. Plain ``StaticFiles`` answers 404 for it; this
    subclass hands back the shell instead and lets the router resolve the path.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or scope["method"] not in ("GET", "HEAD"):
                raise
            if path.startswith("api/") or Path(path).suffix:
                raise
            return await super().get_response("index.html", scope)


@asynccontextmanager
async def lifespan(app: Starlette):
    await setup_state()
    app.state.watches = WatchStore(_store()) if _store() is not None else None
    try:
        yield
    finally:
        await teardown_state()


routes = [
    Route("/api/health", health),
    Route("/api/quota", quota),
    Route("/api/search", search),
    Route("/api/search-author", search_author),
    Route("/api/paper", paper),
    Route("/api/citations", citations),
    Route("/api/references", references),
    Route("/api/related", related),
    Route("/api/network", network),
    Route("/api/metrics", metrics),
    Route("/api/metrics/export", metrics_export),
    Route("/api/metrics/report", metrics_report),
    Route("/api/searches", searches),
    Route("/api/searches/import", search_import, methods=["POST"]),
    Route("/api/searches/export", workspace_export),
    Route("/api/searches/import-workspace", workspace_import, methods=["POST"]),
    Route("/api/searches/{search_id}/export", search_export),
    Route("/api/searches/{search_id}/split", search_split, methods=["POST"]),
    Route("/api/searches/{search_id}/duplicate", search_duplicate, methods=["POST"]),
    Route("/api/searches/{search_id}/replay", search_replay),
    Route("/api/searches/{search_id}", search_delete, methods=["DELETE"]),
    Route("/api/import", import_external, methods=["POST"]),
    Route("/api/cache/clear", cache_clear, methods=["POST"]),
    Route("/api/cache/info", cache_info),
    Route("/api/merge", merge, methods=["POST"]),
    Route("/api/export/graphml", graphml_export),
    Route("/api/export", export, methods=["POST"]),
    Route("/api/identify", identify, methods=["POST"]),
    Route("/api/watches", watches_list_create, methods=["GET", "POST"]),
    Route("/api/watches/{watch_id}", watch_delete, methods=["DELETE"]),
    Route("/api/watches/{watch_id}/feed", watch_feed),
]

if WEB_DIST.is_dir():
    routes.append(
        Mount("/", app=SPAStaticFiles(directory=str(WEB_DIST), html=True), name="web")
    )

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def start() -> None:
    import uvicorn

    uvicorn.run("josc.api:app", host="127.0.0.1", port=8793, reload=False)
