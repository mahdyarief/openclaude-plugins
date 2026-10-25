"""Cache administration and saved-search lifecycle routes.

Split, duplicate and replay all operate on a stored ``search_id``, so they live
next to the cache routes: they are the maintenance surface over the same store.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from .responses import _error
from .state import _int, _providers, _store, _text


async def cache_clear(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    prefix = body.get("prefix") if isinstance(body, dict) else None
    cleared = 0
    providers = _providers()
    cache = getattr(providers[0], "fetcher", None) if providers else None
    ttl_cache = getattr(cache, "cache", None)
    clear = getattr(ttl_cache, "clear", None)
    if callable(clear):
        cleared += clear(prefix)
    store = _store()
    store_clear = getattr(store, "clear", None)
    if callable(store_clear):
        try:
            cleared += await store_clear(prefix)
        except Exception:
            pass
    return JSONResponse({"cleared": cleared})


async def cache_info(request: Request) -> JSONResponse:
    """Per-entry cache metadata for the in-memory and persistent caches."""
    prefix = _text(request, "prefix")
    limit = _int(request, "limit", 200) or 200
    memory = None
    providers = _providers()
    if providers:
        cache = getattr(getattr(providers[0], "fetcher", None), "cache", None)
        info = getattr(cache, "info", None)
        if callable(info):
            memory = info(prefix=prefix, limit=limit)
    persistent = None
    store = _store()
    store_info = getattr(store, "info", None)
    if callable(store_info):
        try:
            persistent = await store_info(prefix=prefix, limit=limit)
        except Exception:
            persistent = None
    return JSONResponse({"memory": memory, "store": persistent})


async def search_split(request: Request) -> JSONResponse:
    store = _store()
    splitter = getattr(store, "split_search", None)
    if not callable(splitter):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))
    try:
        size = int(body.get("size"))
    except (TypeError, ValueError):
        return _error(ValueError("'size' must be an integer."))
    try:
        ids = await splitter(request.path_params["search_id"], size)
    except ValueError as exc:
        return _error(exc)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return JSONResponse({"ids": ids, "count": len(ids)})


async def search_duplicate(request: Request) -> JSONResponse:
    store = _store()
    duplicator = getattr(store, "duplicate_search", None)
    if not callable(duplicator):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        new_id = await duplicator(request.path_params["search_id"])
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if new_id is None:
        return JSONResponse({"error": "Search not found."}, status_code=404)
    return JSONResponse({"id": new_id})


async def search_delete(request: Request) -> JSONResponse:
    """Delete one history row. 404 when the id is unknown."""
    store = _store()
    deleter = getattr(store, "delete_search", None)
    if not callable(deleter):
        return _error(ValueError("Persistent search archive is not configured."))
    search_id = request.path_params["search_id"]
    try:
        deleted = await deleter(search_id)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if not deleted:
        return JSONResponse({"error": "Search not found."}, status_code=404)
    return JSONResponse({"id": search_id, "deleted": True})


async def search_replay(request: Request) -> JSONResponse:
    """Serve a saved search's stored results without touching the network."""
    store = _store()
    replayer = getattr(store, "replay_search", None)
    if not callable(replayer):
        return _error(ValueError("Persistent search archive is not configured."))
    try:
        payload = await replayer(request.path_params["search_id"])
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if payload is None:
        return JSONResponse(
            {"error": "No cached results for this search."}, status_code=404
        )
    return JSONResponse(payload)
