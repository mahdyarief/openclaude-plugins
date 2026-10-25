"""Shared JSON error mapping and store/cache statistics for the HTTP API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from starlette.responses import JSONResponse

from ..models import ProviderError
from .state import OfflineMiss, _providers, _store


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
    store = _store()
    if store is None:
        return None
    stats = getattr(store, "stats", None)
    if not callable(stats):
        return None
    try:
        return await stats()
    except Exception:
        return None
