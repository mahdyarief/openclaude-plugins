"""Persistent query cache backed by Turso/libSQL over the HTTP pipeline API.

The bundled ``libsql_client`` is pinned at 0.3.1 and negotiates the old
``hrana2`` websocket protocol, which current Turso servers reject with a 400
handshake. The plain HTTP pipeline endpoint speaks the same SQL with bound
parameters, so we talk to it directly through ``httpx`` — already a
dependency — and skip the websocket entirely.

Persistence is an optimization, never a correctness requirement: every failure
here degrades to the in-memory cache and must not break a search.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from . import config

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


class TursoCache:
    """TTL key/value cache on top of :class:`TursoStore`."""

    def __init__(self, store: TursoStore, ttl: float):
        self.store = store
        self.ttl = float(ttl)
        self.hits = 0
        self.misses = 0
        self.sets = 0

    async def setup(self) -> None:
        await self.store.execute(
            "CREATE TABLE IF NOT EXISTS query_cache ("
            "key TEXT PRIMARY KEY, "
            "value TEXT NOT NULL, "
            "expires_at REAL NOT NULL)"
        )
        await self.store.execute(
            "CREATE TABLE IF NOT EXISTS searches ("
            "id TEXT PRIMARY KEY, "
            "query TEXT NOT NULL, "
            "author TEXT, "
            "sources TEXT, "
            "filters TEXT, "
            "result_count INTEGER NOT NULL DEFAULT 0, "
            "created_at REAL NOT NULL)"
        )
        await self.store.execute(
            "CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at DESC)"
        )
        # Older deployments created `searches` without the archived payload.
        # SQLite has no IF NOT EXISTS for ADD COLUMN, so swallow the duplicate
        # error that a fresh install raises.
        for column in ("results TEXT", "fingerprint TEXT"):
            try:
                await self.store.execute(f"ALTER TABLE searches ADD COLUMN {column}")
            except Exception:
                pass
        await self.store.execute(
            "CREATE INDEX IF NOT EXISTS idx_searches_fingerprint "
            "ON searches(fingerprint)"
        )

    @staticmethod
    def _key(key: Any) -> str:
        return json.dumps(key, default=str, sort_keys=True)

    async def get(self, key: Any) -> Optional[Any]:
        columns, rows = await self.store.execute(
            "SELECT value, expires_at FROM query_cache WHERE key = ?",
            [self._key(key)],
        )
        if not rows:
            self.misses += 1
            return None
        value, expires_at = rows[0][0], rows[0][1]
        if expires_at is not None and float(expires_at) <= time.time():
            self.misses += 1
            return None
        try:
            result = json.loads(value)
        except (TypeError, ValueError):
            self.misses += 1
            return None
        self.hits += 1
        return result

    async def set(self, key: Any, value: Any) -> None:
        await self.store.execute(
            "INSERT INTO query_cache (key, value, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, expires_at = excluded.expires_at",
            [self._key(key), json.dumps(value), time.time() + self.ttl],
        )
        self.sets += 1

    async def stats(self) -> Dict[str, Any]:
        """Database-backed counts plus process-lifetime hit/miss/set counters."""
        columns, rows = await self.store.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN expires_at <= ? THEN 1 ELSE 0 END) "
            "FROM query_cache",
            [time.time()],
        )
        entries = int(rows[0][0] or 0) if rows and rows[0] else 0
        expired = int(rows[0][1] or 0) if rows and rows[0] else 0
        lookups = self.hits + self.misses
        return {
            "backend": "turso",
            "ttl": self.ttl,
            "entries": entries,
            "expired": expired,
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "hit_rate": round(self.hits / lookups, 3) if lookups else 0.0,
        }

    async def purge_expired(self) -> None:
        await self.store.execute(
            "DELETE FROM query_cache WHERE expires_at <= ?", [time.time()]
        )

    async def clear(self, prefix: Optional[str] = None) -> int:
        """Delete cached queries, optionally only those whose key starts with ``prefix``."""
        if prefix is None:
            _, rows = await self.store.execute("SELECT COUNT(*) FROM query_cache")
            await self.store.execute("DELETE FROM query_cache")
        else:
            pattern = prefix + "%"
            _, rows = await self.store.execute(
                "SELECT COUNT(*) FROM query_cache WHERE key LIKE ?", [pattern]
            )
            await self.store.execute(
                "DELETE FROM query_cache WHERE key LIKE ?", [pattern]
            )
        return int(rows[0][0] or 0) if rows and rows[0] else 0

    async def record_search(
        self,
        query: str,
        author: Optional[str] = None,
        sources: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        result_count: int = 0,
        results: Optional[List[Dict[str, Any]]] = None,
        fingerprint: Optional[str] = None,
    ) -> Optional[str]:
        """Record one search in the history, best-effort.

        When ``fingerprint`` is supplied the row is upserted: a repeat of the
        same query + sources + filters refreshes the existing row instead of
        appending a duplicate. Callers that intentionally create new rows
        (split, duplicate, import) omit the fingerprint and keep appending.

        A Turso hiccup must never break a search, so every failure is swallowed
        just as the module docstring promises. Returns the row id, or ``None``
        when persistence is unavailable.
        """
        payload = (
            query,
            author,
            json.dumps(sources) if sources else None,
            json.dumps(filters) if filters else None,
            result_count,
            json.dumps(results) if results is not None else None,
        )
        try:
            if fingerprint:
                _, rows = await self.store.execute(
                    "SELECT id FROM searches WHERE fingerprint = ?", [fingerprint]
                )
                if rows and rows[0]:
                    existing_id = rows[0][0]
                    await self.store.execute(
                        "UPDATE searches SET query = ?, author = ?, sources = ?, "
                        "filters = ?, result_count = ?, results = ?, created_at = ? "
                        "WHERE id = ?",
                        [*payload, time.time(), existing_id],
                    )
                    return existing_id
            search_id = uuid.uuid4().hex
            await self.store.execute(
                "INSERT INTO searches "
                "(id, query, author, sources, filters, result_count, created_at, "
                "results, fingerprint) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [search_id, *payload[:5], time.time(), payload[5], fingerprint],
            )
        except Exception:
            return None
        return search_id

    @staticmethod
    def _maybe_json(value: Any) -> Any:
        """Decode a JSON column, leaving unparseable text untouched."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    async def list_searches(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent searches, newest first."""
        try:
            _, rows = await self.store.execute(
                "SELECT id, query, author, sources, filters, result_count, "
                "created_at, LENGTH(results) AS size_bytes "
                "FROM searches ORDER BY created_at DESC LIMIT ?",
                [limit],
            )
        except Exception:
            return []
        now = time.time()
        return [
            {
                "id": row[0],
                "query": row[1],
                "author": row[2],
                "sources": self._maybe_json(row[3]),
                "filters": self._maybe_json(row[4]),
                "result_count": row[5],
                "created_at": row[6],
                "size_bytes": int(row[7] or 0),
                "age_seconds": (
                    round(now - float(row[6]), 1) if row[6] is not None else None
                ),
            }
            for row in rows or []
        ]

    async def get_search(self, search_id: str) -> Optional[Dict[str, Any]]:
        """Return one archived search including its stored results."""
        try:
            _, rows = await self.store.execute(
                "SELECT id, query, author, sources, filters, result_count, "
                "created_at, results FROM searches WHERE id = ?",
                [search_id],
            )
        except Exception:
            return None
        if not rows:
            return None
        row = rows[0]
        return {
            "id": row[0],
            "query": row[1],
            "author": row[2],
            "sources": self._maybe_json(row[3]),
            "filters": self._maybe_json(row[4]),
            "result_count": row[5],
            "created_at": row[6],
            "results": self._maybe_json(row[7]),
        }

    async def delete_search(self, search_id: str) -> bool:
        """Delete one archived search. Returns False when the id is unknown."""
        try:
            _, rows = await self.store.execute(
                "SELECT id FROM searches WHERE id = ?", [search_id]
            )
            if not rows or not rows[0]:
                return False
            await self.store.execute(
                "DELETE FROM searches WHERE id = ?", [search_id]
            )
        except Exception:
            return False
        return True

    async def import_search(
        self,
        archive: Dict[str, Any],
        query: str,
        author: Optional[str] = None,
        sources: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        results: Optional[List[Dict[str, Any]]] = None,
        result_count: int = 0,
    ) -> Optional[str]:
        """Store a search archive under a fresh id.

        ``archive`` is accepted for signature symmetry with the export payload;
        only the fields the table persists are written.
        """
        search_id = uuid.uuid4().hex
        try:
            await self.store.execute(
                "INSERT INTO searches "
                "(id, query, author, sources, filters, result_count, created_at, results) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    search_id,
                    query,
                    author,
                    json.dumps(sources) if sources else None,
                    json.dumps(filters) if filters else None,
                    result_count,
                    time.time(),
                    json.dumps(results) if results is not None else None,
                ],
            )
        except Exception:
            return None
        return search_id


    async def duplicate_search(self, search_id: str) -> Optional[str]:
        """Clone an archived search under a fresh id, best-effort."""
        row = await self.get_search(search_id)
        if row is None:
            return None
        new_id = uuid.uuid4().hex
        try:
            await self.store.execute(
                "INSERT INTO searches "
                "(id, query, author, sources, filters, result_count, created_at, results) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    new_id,
                    f"{row['query']} (copy)",
                    row.get("author"),
                    json.dumps(row.get("sources")) if row.get("sources") else None,
                    json.dumps(row.get("filters")) if row.get("filters") else None,
                    row.get("result_count") or 0,
                    time.time(),
                    (
                        json.dumps(row.get("results"))
                        if row.get("results") is not None
                        else None
                    ),
                ],
            )
        except Exception:
            return None
        return new_id

    async def export_workspace(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return full search rows including results, newest first."""
        try:
            _, rows = await self.store.execute(
                "SELECT id, query, author, sources, filters, result_count, "
                "created_at, results FROM searches ORDER BY created_at DESC LIMIT ?",
                [limit],
            )
        except Exception:
            return []
        return [
            {
                "id": row[0],
                "query": row[1],
                "author": row[2],
                "sources": self._maybe_json(row[3]),
                "filters": self._maybe_json(row[4]),
                "result_count": row[5],
                "created_at": row[6],
                "results": self._maybe_json(row[7]),
            }
            for row in rows or []
        ]

    async def import_workspace(self, archive: Dict[str, Any]) -> List[str]:
        """Re-insert every archived search under a fresh id. Never raises."""
        ids: List[str] = []
        for entry in archive.get("searches") or []:
            try:
                new_id = await self.import_search(
                    entry,
                    query=entry.get("query") or "",
                    author=entry.get("author"),
                    sources=entry.get("sources"),
                    filters=entry.get("filters"),
                    results=entry.get("results"),
                    result_count=entry.get("result_count") or 0,
                )
            except Exception:
                new_id = None
            if new_id is not None:
                ids.append(new_id)
        return ids

    async def replay_search(self, search_id: str) -> Optional[Dict[str, Any]]:
        """Return an archived search as a stale "retry from cache" payload."""
        row = await self.get_search(search_id)
        if row is None:
            return None
        results = row.get("results")
        if not results:
            return None
        return {
            "id": row["id"],
            "query": row["query"],
            "author": row.get("author"),
            "sources": row.get("sources"),
            "filters": row.get("filters"),
            "result_count": row.get("result_count"),
            "created_at": row.get("created_at"),
            "results": results,
            "stale": True,
        }

    async def info(
        self, prefix: Optional[str] = None, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Per-entry cache metadata for the ``query_cache`` table."""
        sql = "SELECT key, LENGTH(value), expires_at FROM query_cache"
        args: List[Any] = []
        if prefix is not None:
            sql += " WHERE key LIKE ?"
            args.append(prefix + "%")
        sql += " ORDER BY expires_at ASC LIMIT ?"
        args.append(limit)
        try:
            _, rows = await self.store.execute(sql, args)
        except Exception:
            return []
        now = time.time()
        entries: List[Dict[str, Any]] = []
        for row in rows or []:
            expires_at = float(row[2]) if row[2] is not None else 0.0
            expires_in = round(expires_at - now, 1)
            entries.append(
                {
                    "key": str(row[0]),
                    "size_bytes": int(row[1] or 0),
                    "expires_in_seconds": expires_in,
                    "expired": expires_in <= 0,
                }
            )
        return entries

    async def split_search(self, search_id: str, size: int) -> List[str]:
        """Split an archived search's results into new searches of ``size`` each."""
        row = await self.get_search(search_id)
        if row is None:
            return []
        if size < 1:
            raise ValueError("split size must be at least 1")
        results = row.get("results") or []
        if not results:
            return []
        chunks = [results[i : i + size] for i in range(0, len(results), size)]
        total = len(chunks)
        ids: List[str] = []
        for i, chunk in enumerate(chunks):
            new_id = await self.record_search(
                f"{row['query']} (split {i + 1}/{total})",
                author=row.get("author"),
                sources=row.get("sources"),
                filters=row.get("filters"),
                result_count=len(chunk),
                results=chunk,
            )
            if new_id is not None:
                ids.append(new_id)
        return ids


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
