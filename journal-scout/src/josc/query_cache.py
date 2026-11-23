"""TTL key/value cache on the ``query_cache`` table.

Split out of :mod:`josc.store` so the cache and the search archive stop sharing
one class. :class:`josc.store.TursoCache` composes both behind the original API.
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .store import TursoStore


class QueryCache:
    """TTL key/value cache on the ``query_cache`` table."""

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
