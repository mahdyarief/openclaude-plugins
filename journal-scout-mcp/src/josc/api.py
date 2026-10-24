"""HTTP API for josc-web.

Thin Starlette wrapper around :mod:`josc.aggregator`. Every route maps to one
aggregator call so the browser app and the MCP server stay on the same code
path. Identifiers are passed as query parameters rather than path segments
because DOIs contain slashes.

Run with::

    python -m josc.api            # or: uvicorn josc.api:app --port 8793
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import aggregator, config
from .cache import build_cache
from .exporters import format_papers
from .http import Fetcher
from .models import ProviderError
from .providers import build_providers, provider_names
from .store import build_store, cached_call

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

_state: Dict[str, Any] = {}


class OfflineMiss(Exception):
    """offline=true and the requested key is not in the persistent cache."""


@asynccontextmanager
async def lifespan(app: Starlette):
    ttl = config.get_cache_ttl()
    store = build_store(ttl)
    if store is not None:
        try:
            await store.setup()
            await store.purge_expired()
        except Exception:
            # Persistence is an optimization; an unreachable Turso must not
            # stop the server from serving searches.
            await store.store.close()
            store = None
    fetcher = Fetcher(cache=build_cache(ttl))
    try:
        api_key = config.get_api_key()
    except ValueError:
        api_key = None
    _state["providers"] = build_providers(fetcher, {"api_key": api_key})
    _state["store"] = store
    try:
        yield
    finally:
        await fetcher.close()
        if store is not None:
            await store.store.close()
        _state.clear()


def _providers():
    return _state.get("providers") or []


async def _cached(key: Any, factory: Any, offline: bool = False) -> Any:
    """Memoize a finished aggregator response in Turso (one round-trip)."""
    store = _state.get("store")
    if offline:
        if store is None:
            raise OfflineMiss("Offline mode requested but no persistent cache is configured.")
        try:
            hit = await store.get(key)
        except Exception:
            hit = None
        if hit is None:
            raise OfflineMiss("No cached response for this request; offline mode cannot reach the network.")
        if isinstance(hit, dict):
            return {**hit, "stale": True}
        return hit
    return await cached_call(store, key, factory)


def _flag(request: Request, name: str) -> bool:
    return request.query_params.get(name, "").lower() in ("1", "true", "yes")


def _int(request: Request, name: str, default: Optional[int] = None) -> Optional[int]:
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sources(request: Request) -> Optional[List[str]]:
    raw = request.query_params.getlist("source")
    if not raw:
        raw = request.query_params.getlist("sources")
    values: List[str] = []
    for item in raw:
        values.extend(part.strip() for part in item.split(",") if part.strip())
    return values or None


def _identifier(request: Request) -> str:
    value = (request.query_params.get("identifier") or "").strip()
    if not value:
        raise ValueError("Missing required query parameter 'identifier'.")
    return value


def _error(exc: Exception, status: int = 400) -> JSONResponse:
    if isinstance(exc, OfflineMiss):
        return JSONResponse({"error": str(exc), "offline": True}, status_code=503)
    if isinstance(exc, ProviderError):
        return JSONResponse({"error": exc.message, "provider": exc.provider}, status_code=502)
    return JSONResponse({"error": str(exc)}, status_code=status)


def _cache_stats() -> Optional[Dict[str, Any]]:
    """Report stats from the one fetcher every provider shares, if caching is on."""
    providers = _providers()
    if not providers:
        return None
    cache = getattr(getattr(providers[0], "fetcher", None), "cache", None)
    stats = getattr(cache, "stats", None)
    if not callable(stats):
        return None
    return stats()


async def _store_stats() -> Optional[Dict[str, Any]]:
    """Report the persistent cache, if Turso is configured."""
    store = _state.get("store")
    if store is None:
        return None
    stats = getattr(store, "stats", None)
    if not callable(stats):
        return None
    try:
        return await stats()
    except Exception:
        return None


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
                    "author_search": getattr(p, "supports_author_search", False),
                    "tech_only": getattr(p, "supports_tech_only", False),
                }
                for p in _providers()
            },
        }
    )


async def search(request: Request) -> JSONResponse:
    query = (request.query_params.get("query") or "").strip()
    if not query:
        return _error(ValueError("Missing required query parameter 'query'."))
    limit_per_source = _int(request, "limit_per_source", 10)
    year_from = _int(request, "year_from")
    year_to = _int(request, "year_to")
    tech_only = request.query_params.get("tech_only", "").lower() in ("1", "true", "yes")
    sources = _sources(request)
    offset = _int(request, "offset", 0)
    key = ("search", query, limit_per_source, year_from, year_to, tech_only, sources, offset)
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
            ),
            offline=offline,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a JSON error to the UI
        return _error(exc)
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
        payload = await aggregator.get_paper(_providers(), _identifier(request))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def citations(request: Request) -> JSONResponse:
    try:
        payload = await aggregator.get_citations(
            _providers(), _identifier(request), limit=_int(request, "limit", 20)
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def references(request: Request) -> JSONResponse:
    try:
        payload = await aggregator.get_references(
            _providers(), _identifier(request), limit=_int(request, "limit", 20)
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def network(request: Request) -> Response:
    identifier = _identifier(request)
    limit = _int(request, "limit", 20)
    citing_limit = _int(request, "citing_limit", 10)
    max_nodes = _int(request, "max_nodes", 200)
    graph_format = request.query_params.get("format", "json")
    key = ("network", identifier, limit, citing_limit, max_nodes, graph_format)
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


async def metrics(request: Request) -> JSONResponse:
    author = (request.query_params.get("author") or "").strip() or None
    query = (request.query_params.get("query") or "").strip() or None
    if not (author or query):
        return _error(ValueError("Provide either 'author' or 'query'."))
    limit_per_source = _int(request, "limit_per_source", 50)
    year_from = _int(request, "year_from")
    year_to = _int(request, "year_to")
    sources = _sources(request)
    mode = request.query_params.get("mode") or "basic"
    key = ("metrics", author, query, limit_per_source, year_from, year_to, sources, mode)
    offline = _flag(request, "offline")
    try:
        payload = await _cached(
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
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse(payload)


async def graphml_export(request: Request) -> Response:
    return await network(request)


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


routes = [
    Route("/api/health", health),
    Route("/api/search", search),
    Route("/api/search-author", search_author),
    Route("/api/paper", paper),
    Route("/api/citations", citations),
    Route("/api/references", references),
    Route("/api/network", network),
    Route("/api/metrics", metrics),
    Route("/api/export/graphml", graphml_export),
    Route("/api/export", export, methods=["POST"]),
]

if WEB_DIST.is_dir():
    routes.append(Mount("/", app=StaticFiles(directory=str(WEB_DIST), html=True), name="web"))

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


if __name__ == "__main__":
    start()
