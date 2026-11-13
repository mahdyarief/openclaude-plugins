"""Process-wide state, cache plumbing and request helpers for the HTTP API.

Every route module reads providers and the persistent store from :data:`_state`
so the tests can substitute both with ``monkeypatch.setitem``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from starlette.requests import Request

from ..config import get_api_key, get_cache_ttl
from ..cache import build_cache
from ..http import Fetcher
from ..providers import build_providers
from ..store import build_store, cached_call


class OfflineMiss(Exception):
    """offline=true and the requested key is not in the persistent cache."""


_state: Dict[str, Any] = {}


async def setup_state() -> None:
    """Build providers and the persistent store once per app lifespan."""
    ttl = get_cache_ttl()
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
        api_key = get_api_key()
    except ValueError:
        api_key = None
    _state["providers"] = build_providers(fetcher, {"api_key": api_key})
    _state["store"] = store
    _state["fetcher"] = fetcher


async def teardown_state() -> None:
    fetcher = _state.get("fetcher")
    store = _state.get("store")
    if fetcher is not None:
        await fetcher.close()
    if store is not None:
        await store.store.close()
    _state.clear()


def _providers():
    return _state.get("providers") or []


def _store():
    return _state.get("store")


async def _cached(key: Any, factory: Any, offline: bool = False) -> Any:
    """Memoize a finished aggregator response in Turso (one round-trip)."""
    store = _store()
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


# --- request parsing ---------------------------------------------------------


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


def _text(request: Request, name: str) -> Optional[str]:
    value = (request.query_params.get(name) or "").strip()
    return value or None


def _identifier(request: Request) -> str:
    value = (request.query_params.get("identifier") or "").strip()
    if not value:
        raise ValueError("Missing required query parameter 'identifier'.")
    return value
