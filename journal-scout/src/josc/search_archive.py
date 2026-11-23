"""Archive of completed searches on the ``searches`` table.

Split out of :mod:`josc.store` so the search archive and the query cache stop
sharing one class. :class:`josc.store.TursoCache` composes both behind the
original API.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .store import TursoStore


class SearchArchive:
    """Archive of completed searches on the ``searches`` table."""

    def __init__(self, store: TursoStore):
        self.store = store

    async def setup(self) -> None:
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
    def _maybe_json(value: Any) -> Any:
        """Decode a JSON column, leaving unparseable text untouched."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

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
