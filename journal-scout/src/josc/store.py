"""Persistent storage backed by Turso/libSQL over the HTTP pipeline API.

The bundled ``libsql_client`` is pinned at 0.3.1 and negotiates the old
``hrana2`` websocket protocol, which current Turso servers reject with a 400
handshake. The plain HTTP pipeline endpoint speaks the same SQL with bound
parameters, so we talk to it directly through ``httpx`` — already a
dependency — and skip the websocket entirely.

Persistence is an optimization, never a correctness requirement: every failure
here degrades to the in-memory cache and must not break a search.

Two tables live behind one transport. :class:`~josc.query_cache.QueryCache`
owns ``query_cache`` and :class:`~josc.search_archive.SearchArchive` owns
``searches``. :class:`TursoCache` keeps the historical single-object surface by
inheriting both, because every route reaches it through ``getattr(store, ...)``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from . import config
from .query_cache import QueryCache
from .search_archive import SearchArchive

DEFAULT_TIMEOUT = 5.0


def _cell(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    # Turso's pipeline JSON wants a real number here, not a quoted string.
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _decode(cell: Dict[str, Any]) -> Any:
    kind = cell.get("type")
    if kind == "null":
        return None
    value = cell.get("value")
    if kind == "integer":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "blob":
        return value
    return value


class TursoStore:
    """Minimal async client for Turso's ``/v2/pipeline`` endpoint."""

    def __init__(
        self,
        url: str,
        token: str,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        base = url.replace("libsql://", "https://").rstrip("/")
        self.endpoint = f"{base}/v2/pipeline"
        self.token = token
        self._client = client
        self._owns_client = client is None
        self._timeout = timeout

    async def _post(self, requests: Sequence[Dict[str, Any]]) -> List[Any]:
        body = {"requests": list(requests) + [{"type": "close"}]}
        headers = {"Authorization": f"Bearer {self.token}"}
        if self._client is not None:
            response = await self._client.post(self.endpoint, json=body, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self.endpoint, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
        results: List[Any] = []
        for item in payload.get("results") or []:
            if item.get("type") != "ok":
                raise RuntimeError(str(item.get("error") or item)[:300])
            body_item = item.get("response") or {}
            if body_item.get("type") != "execute":
                results.append(None)
                continue
            result = body_item.get("result") or {}
            columns = [col.get("name") for col in result.get("cols") or []]
            rows = [
                [_decode(cell) for cell in row] for row in result.get("rows") or []
            ]
            results.append((columns, rows))
        return results

    @staticmethod
    def _statement(sql: str, args: Optional[Sequence[Any]]) -> Dict[str, Any]:
        stmt: Dict[str, Any] = {"sql": sql}
        if args:
            stmt["args"] = [_cell(arg) for arg in args]
        return {"type": "execute", "stmt": stmt}

    async def execute(
        self, sql: str, args: Optional[Sequence[Any]] = None
    ) -> Tuple[List[str], List[List[Any]]]:
        results = await self._post([self._statement(sql, args)])
        first = results[0] if results else None
        return first if first else ([], [])

    async def execute_many(
        self, statements: Sequence[Tuple[str, Optional[Sequence[Any]]]]
    ) -> List[Any]:
        return await self._post([self._statement(sql, args) for sql, args in statements])

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()


class TursoCache(QueryCache, SearchArchive):
    """Single entry point over the query cache and the search archive.

    Inherits both capabilities so existing ``getattr(store, "<method>")`` call
    sites keep working; the two domains no longer share an implementation.
    """

    def __init__(self, store: TursoStore, ttl: float):
        QueryCache.__init__(self, store, ttl)

    async def setup(self) -> None:
        await QueryCache.setup(self)
        await SearchArchive.setup(self)


def build_store(ttl: float) -> Optional[TursoCache]:
    """Return a persistent cache, or ``None`` when Turso is not configured."""
    url = config.get_turso_url()
    token = config.get_turso_token()
    if not url or not token or ttl <= 0:
        return None
    return TursoCache(TursoStore(url, token), ttl)


async def cached_call(cache: Optional[TursoCache], key: Any, factory: Any) -> Any:
    """Return ``cache[key]``, otherwise run ``factory()`` and persist its result.

    Persistence wraps the *finished* response, not each upstream request: a
    Turso round-trip costs 1.4-2.4s, so caching per HTTP call would add minutes
    to a single search. One lookup per user request is the right granularity.
    """
    if cache is not None:
        try:
            hit = await cache.get(key)
        except Exception:
            hit = None
        if hit is not None:
            return hit
    value = await factory()
    if cache is not None:
        try:
            await cache.set(key, value)
        except Exception:
            pass
    return value
