# Saved-Search Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengubah arsip pencarian yang sudah ada menjadi pemantauan literatur berkelanjutan: sebuah watch menyimpan query, dijalankan ulang secara berkala, lalu melaporkan paper yang belum pernah terlihat — plus feed RSS untuk pembaca feed.

**Architecture:** Tiga lapis. `src/josc/watch_diff.py` berisi fungsi murni (fingerprint, key set, diff, render RSS). `src/josc/watches.py` berisi `WatchStore` (tabel `search_watches`) dan `check_watch()` yang menerima callable pencarian sehingga test tidak menyentuh jaringan. `src/josc/api/watch_routes.py` mengekspos REST, dan satu tool MCP `check_watches` menjalankan semua watch aktif. Tidak ada scheduler bawaan: pemanggil (cron, MCP client, atau UI) yang menentukan kapan `check` dijalankan.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`), Starlette (extra `web`).

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- Tidak ada dependensi runtime baru; RSS dirender dengan `xml.sax.saxutils.escape` dari standard library.
- Tidak boleh ada panggilan jaringan di test; runner pencarian selalu diinjeksikan.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- Setiap task berakhir dengan satu commit terpisah.

### Keputusan cakupan yang disengaja

Zotero punya `feedReader.js` dengan model feed penuh: sinkronisasi berkala, status baca, penyaringan duplikat lintas feed, dan UI. Plan ini **tidak** memport itu. Yang diambil hanya idenya: satu query tersimpan + jadwal + laporan item baru + output feed. Tidak ada scheduler internal, tidak ada status baca, tidak ada sinkronisasi lintas perangkat.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/watch_diff.py` | `watch_fingerprint()`, `result_keys()`, `diff_results()`, `render_rss()` — fungsi murni |
| `src/josc/watches.py` | `WatchStore` (DDL + CRUD) dan `check_watch()` |
| `src/josc/api/watch_routes.py` | Handler REST: list/create, delete, check, feed |
| `src/josc/api/app.py` | Registrasi route |
| `src/josc/api/__init__.py` | Re-export handler |
| `src/josc/server.py` | Tool MCP `check_watches` |
| `tests/test_watches.py` | Semua test untuk irisan ini |

---

### Task 1: Pure diff and RSS rendering

**Files:**
- Create: `src/josc/watch_diff.py`
- Test: `tests/test_watches.py`

**Interfaces:**
- Consumes: `normalize_doi()` dan `normalize_title()` dari `josc.utils`.
- Produces:
  - `watch_fingerprint(query: str, author: str | None, sources: list[str] | None, filters: dict | None) -> str` — SHA-256 hex yang stabil terhadap urutan kunci `filters` dan urutan `sources`.
  - `result_keys(results: Sequence[dict]) -> set[str]` — himpunan identitas paper (`doi:...` bila ada, selain itu `title:...`).
  - `diff_results(previous: set[str], current: Sequence[dict]) -> list[dict]` — hanya paper yang key-nya belum ada di `previous`, urutan dipertahankan.
  - `render_rss(title: str, link: str, items: Sequence[dict]) -> str` — dokumen RSS 2.0 minimal, semua teks di-escape.

- [ ] **Step 1: Write the failing test**

Create `tests/test_watches.py`:

```python
from josc.watch_diff import diff_results, render_rss, result_keys, watch_fingerprint


def test_fingerprint_is_stable_across_dict_key_order():
    a = watch_fingerprint("q", None, ["crossref", "openalex"], {"year_from": 2020})
    b = watch_fingerprint("q", None, ["openalex", "crossref"], {"year_from": 2020})
    assert a == b
    assert len(a) == 64


def test_fingerprint_changes_when_query_changes():
    assert watch_fingerprint("a", None, None, None) != watch_fingerprint("b", None, None, None)


def test_result_keys_prefers_doi_and_falls_back_to_title():
    keys = result_keys(
        [
            {"doi": "https://doi.org/10.1/ABC", "title": "One"},
            {"title": "Attention Is All You Need!"},
        ]
    )
    assert keys == {"doi:10.1/abc", "title:attention is all you need"}


def test_diff_results_returns_only_unseen_papers():
    previous = {"doi:10.1/old"}
    current = [
        {"doi": "10.1/old", "title": "Old"},
        {"doi": "10.1/new", "title": "New"},
    ]
    fresh = diff_results(previous, current)
    assert [paper["title"] for paper in fresh] == ["New"]


def test_render_rss_escapes_markup():
    out = render_rss(
        "Watch & Roll",
        "https://example.test/feed",
        [{"title": "A <b>Title</b>", "url": "https://example.test/a?x=1&y=2"}],
    )
    assert out.startswith("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
    assert "Watch &amp; Roll" in out
    assert "A &lt;b&gt;Title&lt;/b&gt;" in out
    assert "x=1&amp;y=2" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watches.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.watch_diff'`.

- [ ] **Step 3: Create `src/josc/watch_diff.py`**

```python
"""Pure helpers for saved-search watches.

A watch stores the query that produced a result set and remembers which papers
it has already reported. Nothing here touches storage or the network, so the
diff and feed behaviour can be tested in isolation.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Set
from xml.sax.saxutils import escape

from .utils import normalize_doi, normalize_title


def watch_fingerprint(
    query: str,
    author: Optional[str],
    sources: Optional[List[str]],
    filters: Optional[Dict[str, Any]],
) -> str:
    """Return a stable identity for one watch definition."""
    payload = {
        "query": query or "",
        "author": author or "",
        "sources": sorted(sources or []),
        "filters": filters or {},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _paper_key(paper: Dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.get('title'))}"


def result_keys(results: Sequence[Dict[str, Any]]) -> Set[str]:
    """Return the identity keys for a batch of paper dicts."""
    return {_paper_key(paper) for paper in results}


def diff_results(
    previous: Set[str], current: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return the papers in ``current`` whose keys are not in ``previous``."""
    return [paper for paper in current if _paper_key(paper) not in previous]


def render_rss(title: str, link: str, items: Sequence[Dict[str, Any]]) -> str:
    """Render a minimal RSS 2.0 document for a watch result set."""
    entries: List[str] = []
    for paper in items:
        paper_title = escape(paper.get("title") or "(untitled)")
        paper_link = escape(paper.get("url") or link)
        entries.append(
            "<item>"
            f"<title>{paper_title}</title>"
            f"<link>{paper_link}</link>"
            f"<guid>{paper_link}</guid>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{escape(title)}</title>"
        f"<link>{escape(link)}</link>"
        "<description>Saved-search watch results</description>"
        + "".join(entries)
        + "</channel></rss>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watches.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/watch_diff.py tests/test_watches.py
git commit -m "feat(watches): add pure diff and RSS helpers"
```

---

### Task 2: Store watches and run a check without touching the network

**Files:**
- Create: `src/josc/watches.py`
- Test: `tests/test_watches.py` (append)

**Interfaces:**
- Consumes: `watch_fingerprint()`, `result_keys()`, `diff_results()` dari Task 1; objek `store` dengan `async def execute(sql, params) -> tuple`.
- Produces:
  - `WATCH_SCHEMA: str` — DDL untuk tabel `search_watches`.
  - `WatchStore(store)` dengan `async setup()`, `async create(query, author=None, sources=None, filters=None) -> str`, `async list() -> list[dict]`, `async delete(watch_id) -> bool`, `async get(watch_id) -> dict | None`, `async mark_seen(watch_id, keys: set[str], results: list[dict]) -> None`.
  - `check_watch(watch: dict, runner, store) -> dict` — async; `runner` adalah `Callable[[dict], Awaitable[list[dict]]]`. Selain mengembalikan paper baru, ia juga mempersist `last_results` agar feed REST bisa membacanya tanpa jaringan.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_watches.py`:

```python
import pytest

from josc.watches import WATCH_SCHEMA, WatchStore, check_watch


class FakeStore:
    """In-memory stand-in for the Turso store used by WatchStore."""

    def __init__(self):
        self.rows = {}

    async def execute(self, sql, params):
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("create table"):
            return None, []
        if normalized.startswith("insert into search_watches"):
            watch_id, query, author, sources, filters, seen, last_results, created_at = params
            self.rows[watch_id] = {
                "id": watch_id,
                "query": query,
                "author": author,
                "sources": sources,
                "filters": filters,
                "seen": seen,
                "last_results": last_results,
                "created_at": created_at,
            }
            return None, []
        if normalized.startswith("select id, query, author, sources, filters, seen"):
            return None, [
                (
                    row["id"],
                    row["query"],
                    row["author"],
                    row["sources"],
                    row["filters"],
                    row["seen"],
                    row["last_results"],
                    row["created_at"],
                )
                for row in self.rows.values()
            ]
        if normalized.startswith("update search_watches"):
            seen, last_results, watch_id = params
            if watch_id in self.rows:
                self.rows[watch_id]["seen"] = seen
                self.rows[watch_id]["last_results"] = last_results
            return None, []
        if normalized.startswith("delete from search_watches"):
            self.rows.pop(params[0], None)
            return None, []
        raise AssertionError(f"unexpected SQL: {sql}")


def test_watch_schema_declares_the_table():
    assert "search_watches" in WATCH_SCHEMA
    assert "fingerprint" in WATCH_SCHEMA


async def test_create_list_and_delete_round_trip():
    store = FakeStore()
    watches = WatchStore(store)
    await watches.setup()

    watch_id = await watches.create("graph neural networks", sources=["openalex"])
    listed = await watches.list()
    assert len(listed) == 1
    assert listed[0]["query"] == "graph neural networks"

    assert await watches.delete(watch_id) is True
    assert await watches.list() == []


async def test_check_watch_reports_only_new_papers_and_marks_them_seen():
    store = FakeStore()
    watches = WatchStore(store)
    await watches.setup()
    watch_id = await watches.create("q")
    watch = await watches.get(watch_id)

    async def runner(_watch):
        return [
            {"doi": "10.1/old", "title": "Old"},
            {"doi": "10.1/new", "title": "New"},
        ]

    await watches.mark_seen(watch_id, {"doi:10.1/old"}, [])
    watch = await watches.get(watch_id)
    result = await check_watch(watch, runner, watches)

    assert [paper["title"] for paper in result["new"]] == ["New"]
    refreshed = await watches.get(watch_id)
    assert "doi:10.1/new" in refreshed["seen"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watches.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.watches'`.

- [ ] **Step 3: Create `src/josc/watches.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watches.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/watches.py tests/test_watches.py
git commit -m "feat(watches): persist watches and diff runs without network access"
```

---

### Task 3: Expose REST endpoints for watches

**Files:**
- Create: `src/josc/api/watch_routes.py`
- Modify: `src/josc/api/app.py`
- Modify: `src/josc/api/__init__.py`
- Test: `tests/test_watch_routes.py`

**Interfaces:**
- Consumes: `WatchStore` dari `josc.watches`; `render_rss()` dari `josc.watch_diff`; `_error()` dari `josc.api.responses`.
- Produces: handler `watches_list_create`, `watch_delete`, `watch_feed` yang dipakai `app.py`. Tidak ada handler check di REST karena runner pencarian hanya hidup di jalur MCP (`check_watches`); route check akan menjadi endpoint yang selalu mengembalikan data basi.

- [ ] **Step 1: Write the failing test**

Create `tests/test_watch_routes.py`:

```python
from josc.api.watch_routes import watch_feed


def test_watch_feed_renders_persisted_results_without_network():
    class FakeWatchStore:
        async def get(self, watch_id):
            return {
                "id": watch_id,
                "query": "graph neural networks",
                "seen": {"doi:10.1/a"},
                "last_results": [{"doi": "10.1/a", "title": "Old Paper"}],
            }

    class FakeRequest:
        path_params = {"watch_id": "abc"}
        app = type("App", (), {"state": type("S", (), {"watches": FakeWatchStore()})()})()

    response = __import__("asyncio").run(watch_feed(FakeRequest()))
    assert response.media_type == "application/rss+xml"
    assert b"<rss" in response.body
    assert b"Old Paper" in response.body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_watch_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.api.watch_routes'`.

- [ ] **Step 3: Create `src/josc/api/watch_routes.py`**

```python
"""REST handlers for saved-search watches.

The check itself lives in the MCP tool, because only that path has a search
runner. REST can create, list, delete and serve the last persisted result set.
"""

import json
from typing import Any

from starlette.responses import JSONResponse, Response

from ..watch_diff import render_rss
from .responses import _error


def _watches(request: Any):
    return request.app.state.watches


async def watches_list_create(request: Any):
    store = _watches(request)
    if request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return _error("invalid JSON body", 400)
        query = (body.get("query") or "").strip()
        if not query:
            return _error("query is required", 400)
        watch_id = await store.create(
            query,
            author=body.get("author"),
            sources=body.get("sources"),
            filters=body.get("filters"),
        )
        return JSONResponse({"id": watch_id}, status_code=201)
    return JSONResponse({"watches": await store.list()})


async def watch_delete(request: Any):
    store = _watches(request)
    deleted = await store.delete(request.path_params["watch_id"])
    if not deleted:
        return _error("watch not found", 404)
    return JSONResponse({"deleted": True})


async def watch_feed(request: Any):
    store = _watches(request)
    watch = await store.get(request.path_params["watch_id"])
    if watch is None:
        return _error("watch not found", 404)
    body = render_rss(
        f"Watch: {watch['query']}",
        f"/api/watches/{watch['id']}/feed",
        watch.get("last_results") or [],
    )
    return Response(body, media_type="application/rss+xml")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_watch_routes.py -v`
Expected: PASS — 1 passed.

- [ ] **Step 5: Register the routes**

In `src/josc/api/app.py`, add these imports beside the other route imports:

```python
from .watch_routes import watch_delete, watch_feed, watches_list_create
```

Then add these entries to the `routes` list, after the search routes:

```python
    Route("/api/watches", watches_list_create, methods=["GET", "POST"]),
    Route("/api/watches/{watch_id}", watch_delete, methods=["DELETE"]),
    Route("/api/watches/{watch_id}/feed", watch_feed),
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 7: Commit**

```bash
git add src/josc/api/watch_routes.py src/josc/api/app.py tests/test_watch_routes.py
git commit -m "feat(watches): expose REST endpoints for saved-search watches"
```

---

### Task 4: Expose `check_watches` as an MCP tool

**Files:**
- Modify: `src/josc/server.py`
- Test: `tests/test_server.py` (append)

**Interfaces:**
- Consumes: `WatchStore`, `check_watch()` dari `josc.watches`; `_store()` dari `josc.api.state`; parameter `providers` yang sudah diterima `build_json`; `aggregator.search_all` yang sudah ada.
- Produces: tool MCP `check_watches` tanpa argumen wajib; hasilnya `{"watches": [{"id": str, "checked": int, "new": list[dict]}]}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py`:

```python
async def test_check_watches_tool_is_registered():
    assert "check_watches" in TOOL_NAMES


async def test_check_watches_returns_new_items_per_watch(monkeypatch):
    import josc.server as server

    class FakeWatchStore:
        def __init__(self):
            self.seen = set()
            self.last_results = []

        async def list(self):
            return [
                {
                    "id": "w1",
                    "query": "q",
                    "seen": set(self.seen),
                    "last_results": list(self.last_results),
                }
            ]

        async def get(self, watch_id):
            return {
                "id": watch_id,
                "query": "q",
                "seen": set(self.seen),
                "last_results": list(self.last_results),
            }

        async def mark_seen(self, watch_id, keys, results):
            self.seen |= set(keys)
            self.last_results = list(results)

    fake_store = FakeWatchStore()
    monkeypatch.setattr(server, "_watch_store", lambda: fake_store, raising=False)

    async def fake_search_all(providers, **kwargs):
        return [Paper(doi="10.1/new", title="New")], [], {}

    monkeypatch.setattr(server.aggregator, "search_all", fake_search_all)

    result = await build_json("check_watches", {}, [], None)
    assert result["watches"][0]["checked"] == 1
    assert result["watches"][0]["new"][0]["title"] == "New"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `assert "check_watches" in TOOL_NAMES`.

- [ ] **Step 3: Register the tool name and schema**

In `src/josc/server.py`, add `"check_watches",` to `UNIFIED_TOOLS`. Then inside `_tool_list()`, append:

```python
        _search_tool(
            "check_watches",
            "Run every saved-search watch and return papers not reported before.",
            {"type": "object", "properties": {}},
        ),
```

- [ ] **Step 4: Add the dispatch branch**

At the top of `src/josc/server.py`, add:

```python
from .api.state import _store
from .watches import WatchStore, check_watch
```

Then add this helper above `build_json`:

```python
def _watch_store() -> WatchStore:
    return WatchStore(_store())
```

Inside `build_json`, before the `export_results` branch, add:

```python
    if name == "check_watches":
        store = _watch_store()

        async def runner(watch):
            papers, _errors, _counts = await aggregator.search_all(
                providers,
                query=watch["query"],
                author=watch.get("author"),
                sources=watch.get("sources"),
                filters=watch.get("filters"),
            )
            return [paper.to_dict() for paper in papers]

        reports = []
        for watch in await store.list():
            result = await check_watch(watch, runner, store)
            reports.append(
                {
                    "id": watch["id"],
                    "checked": result["checked"],
                    "new": result["new"],
                }
            )
        return {"watches": reports}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS — kedua test baru hijau.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — termasuk assertion jumlah tool yang sudah diperbarui di irisan 04.

- [ ] **Step 7: Commit**

```bash
git add src/josc/server.py tests/test_server.py
git commit -m "feat(watches): expose check_watches MCP tool"
```

---

## Self-review

- **Cakupan:** fungsi murni diff + RSS (Task 1), persistensi + `check_watch` (Task 2), REST (Task 3), tool MCP (Task 4). Model feed Zotero disederhanakan sesuai keputusan cakupan.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `WatchStore.create()` mengembalikan `str`; `get()` mengembalikan `dict | None` dengan kunci `seen` berupa `set[str]`; `check_watch()` menerima `Callable[[dict], Awaitable[list[dict]]]` dan mengembalikan `dict` berisi `new` dan `checked`. Task 4 memakai bentuk yang sama.
- **Catatan eksekusi:** `check_watch` mempersist `last_results` setiap kali dijalankan, dan `watch_feed` hanya membaca kolom itu — tidak ada pemanggilan jaringan di route. Penjadwalan nyata dilakukan pemanggil eksternal lewat `check_watches`.
