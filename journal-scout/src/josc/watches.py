"""Saved-search watches: persistence plus a network-free check function.

The caller supplies the search runner, so this module never imports a provider
or an HTTP client. A watch simply remembers which paper keys it has already
reported and asks the runner for the current result set.
"""

import json
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from .watch_diff import diff_results, result_keys, watch_fingerprint

WATCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_watches (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    author TEXT,
    sources TEXT,
    filters TEXT,
    seen TEXT,
    last_results TEXT,
    fingerprint TEXT NOT NULL,
    created_at REAL NOT NULL
)
"""


class WatchStore:
    """CRUD for the ``search_watches`` table."""

    def __init__(self, store: Any):
        self.store = store

    async def setup(self) -> None:
        await self.store.execute(WATCH_SCHEMA, [])

    async def create(
        self,
        query: str,
        author: Optional[str] = None,
        sources: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        watch_id = uuid.uuid4().hex
        fingerprint = watch_fingerprint(query, author, sources, filters)
        await self.store.execute(
            "INSERT INTO search_watches "
            "(id, query, author, sources, filters, seen, last_results, fingerprint, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                watch_id,
                query,
                author,
                json.dumps(sources) if sources else None,
                json.dumps(filters) if filters else None,
                json.dumps([]),
                json.dumps([]),
                fingerprint,
                time.time(),
            ],
        )
        return watch_id

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        return {
            "id": row[0],
            "query": row[1],
            "author": row[2],
            "sources": json.loads(row[3]) if row[3] else None,
            "filters": json.loads(row[4]) if row[4] else None,
            "seen": set(json.loads(row[5]) if row[5] else []),
            "last_results": json.loads(row[6]) if row[6] else [],
            "created_at": row[7],
        }

    async def list(self) -> List[Dict[str, Any]]:
        _, rows = await self.store.execute(
            "SELECT id, query, author, sources, filters, seen, last_results, created_at "
            "FROM search_watches ORDER BY created_at DESC",
            [],
        )
        return [self._row_to_dict(row) for row in rows or []]

    async def get(self, watch_id: str) -> Optional[Dict[str, Any]]:
        for row in await self.list():
            if row["id"] == watch_id:
                return row
        return None

    async def delete(self, watch_id: str) -> bool:
        existing = await self.get(watch_id)
        if existing is None:
            return False
        await self.store.execute(
            "DELETE FROM search_watches WHERE id = ?", [watch_id]
        )
        return True

    async def mark_seen(
        self,
        watch_id: str,
        keys: Set[str],
        results: List[Dict[str, Any]],
    ) -> None:
        current = await self.get(watch_id)
        if current is None:
            return
        merged = current["seen"] | set(keys)
        await self.store.execute(
            "UPDATE search_watches SET seen = ?, last_results = ? WHERE id = ?",
            [json.dumps(sorted(merged)), json.dumps(results), watch_id],
        )


async def check_watch(
    watch: Dict[str, Any],
    runner: Callable[[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]],
    store: WatchStore,
) -> Dict[str, Any]:
    """Run one watch and return the papers not reported before."""
    current = await runner(watch)
    fresh = diff_results(watch["seen"], current)
    if fresh:
        await store.mark_seen(watch["id"], result_keys(fresh), current)
    return {"watch": watch, "new": fresh, "checked": len(current)}
