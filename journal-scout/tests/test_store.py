import json

import httpx

from josc.store import TursoCache, TursoStore, _cell, cached_call


def _pipeline(rows=None, columns=None):
    """Build a Turso /v2/pipeline response with one execute result."""
    return {
        "baton": None,
        "base_url": None,
        "results": [
            {
                "type": "ok",
                "response": {
                    "type": "execute",
                    "result": {
                        "cols": [{"name": name} for name in (columns or [])],
                        "rows": rows or [],
                        "affected_row_count": 0,
                        "last_insert_rowid": None,
                        "replication_index": None,
                        "rows_read": 0,
                        "rows_written": 0,
                        "query_duration_ms": 0.1,
                    },
                },
            },
            {"type": "ok", "response": {"type": "close"}},
        ],
    }


def _store(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TursoStore("libsql://example.test", "token", client=client)


def test_float_cell_is_a_json_number_not_a_string():
    cell = _cell(1792812742.2094605)
    assert cell == {"type": "float", "value": 1792812742.2094605}
    # Turso rejects a quoted float with HTTP 400, so this must serialise bare.
    assert json.dumps(cell) == '{"type": "float", "value": 1792812742.2094605}'


def test_execute_decodes_rows_and_sends_bound_args():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json=_pipeline(
                rows=[[{"type": "text", "value": "world"}, {"type": "integer", "value": "3"}]],
                columns=["value", "n"],
            ),
        )

    store = _store(handler)

    import asyncio

    columns, rows = asyncio.run(store.execute("SELECT value, n FROM t WHERE k = ?", ["k1"]))
    asyncio.run(store.close())

    assert columns == ["value", "n"]
    assert rows == [["world", 3]]
    assert seen["auth"] == "Bearer token"
    request = seen["body"]["requests"][0]
    assert request["stmt"]["args"] == [{"type": "text", "value": "k1"}]
    assert seen["body"]["requests"][-1] == {"type": "close"}


def test_cache_roundtrip_and_expiry():
    import asyncio

    store = TursoStore(
        "libsql://example.test",
        "token",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json=_pipeline(
                        rows=[[{"type": "text", "value": '{"a": 1}'}, {"type": "float", "value": 9999999999.0}]],
                        columns=["value", "expires_at"],
                    ),
                )
            )
        ),
    )
    cache = TursoCache(store, ttl=60)
    key = ("crossref", "https://example.test", (("q", "a"),))

    assert asyncio.run(cache.get(key)) == {"a": 1}
    assert cache._key(key) == '["crossref", "https://example.test", [["q", "a"]]]'
    asyncio.run(store.close())


def test_cached_call_serves_a_hit_without_running_the_factory():
    import asyncio

    calls = {"factory": 0, "get": 0, "set": 0}

    class FakeStore:
        async def get(self, key):
            calls["get"] += 1
            return {"ok": True, "from": "turso"}

        async def set(self, key, value):
            calls["set"] += 1

    async def factory():
        calls["factory"] += 1
        return {"ok": True, "from": "upstream"}

    payload = asyncio.run(cached_call(FakeStore(), ("k",), factory))

    assert payload == {"ok": True, "from": "turso"}
    assert calls == {"factory": 0, "get": 1, "set": 0}


def test_cached_call_persists_a_miss_and_survives_a_broken_store():
    import asyncio

    calls = {"factory": 0, "set": 0}

    class BrokenStore:
        async def get(self, key):
            raise RuntimeError("turso down")

        async def set(self, key, value):
            calls["set"] += 1
            raise RuntimeError("turso down")

    async def factory():
        calls["factory"] += 1
        return {"ok": True}

    payload = asyncio.run(cached_call(BrokenStore(), ("k",), factory))

    assert payload == {"ok": True}
    assert calls == {"factory": 1, "set": 1}


def test_cached_call_without_a_store_just_runs_the_factory():
    import asyncio

    async def factory():
        return {"ok": True}

    assert asyncio.run(cached_call(None, ("k",), factory)) == {"ok": True}


def _count_pipeline(count):
    return _pipeline(
        rows=[[{"type": "integer", "value": str(count)}]], columns=["COUNT(*)"]
    )


def test_cache_clear_deletes_everything_and_returns_count():
    import asyncio

    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body["requests"][0]["stmt"])
        if "COUNT(*)" in seen[-1]["sql"]:
            return httpx.Response(200, json=_count_pipeline(3))
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    assert asyncio.run(cache.clear()) == 3
    assert seen[0]["sql"] == "SELECT COUNT(*) FROM query_cache"
    assert seen[1]["sql"] == "DELETE FROM query_cache"


def test_cache_clear_with_prefix_uses_a_parameterised_like_delete():
    import asyncio

    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body["requests"][0]["stmt"])
        if "COUNT(*)" in seen[-1]["sql"]:
            return httpx.Response(200, json=_count_pipeline(2))
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    assert asyncio.run(cache.clear("abc")) == 2
    for stmt in seen:
        assert "LIKE ?" in stmt["sql"]
        assert stmt["args"] == [{"type": "text", "value": "abc%"}]


def _search_row(results):
    return [
        {"type": "text", "value": "old"},
        {"type": "text", "value": "quantum"},
        {"type": "text", "value": "smith"},
        {"type": "text", "value": '["crossref"]'},
        {"type": "text", "value": '{"year": 2024}'},
        {"type": "integer", "value": str(len(results))},
        {"type": "float", "value": 1700000000.0},
        {"type": "text", "value": json.dumps(results)},
    ]


def test_split_search_chunks_results_and_inserts_each_chunk():
    import asyncio

    results = [{"title": f"p{i}"} for i in range(5)]
    inserts = []

    def handler(request):
        stmt = json.loads(request.content)["requests"][0]["stmt"]
        if stmt["sql"].startswith("SELECT id"):
            return httpx.Response(
                200,
                json=_pipeline(
                    rows=[_search_row(results)],
                    columns=[
                        "id",
                        "query",
                        "author",
                        "sources",
                        "filters",
                        "result_count",
                        "created_at",
                        "results",
                    ],
                ),
            )
        inserts.append(stmt)
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    ids = asyncio.run(cache.split_search("old", 2))

    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert len(inserts) == 3
    chunk_sizes = [int(stmt["args"][5]["value"]) for stmt in inserts]
    assert chunk_sizes == [2, 2, 1]
    labels = [stmt["args"][1]["value"] for stmt in inserts]
    assert labels == [
        "quantum (split 1/3)",
        "quantum (split 2/3)",
        "quantum (split 3/3)",
    ]


def test_split_search_returns_empty_list_for_missing_row():
    import asyncio

    def handler(request):
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    assert asyncio.run(cache.split_search("missing", 2)) == []


def test_split_search_rejects_size_below_one():
    import asyncio

    import pytest

    def handler(request):
        return httpx.Response(
            200,
            json=_pipeline(
                rows=[_search_row([{"title": "p0"}])],
                columns=[
                    "id",
                    "query",
                    "author",
                    "sources",
                    "filters",
                    "result_count",
                    "created_at",
                    "results",
                ],
            ),
        )

    cache = TursoCache(_store(handler), ttl=60)
    with pytest.raises(ValueError):
        asyncio.run(cache.split_search("old", 0))


def _search_columns():
    return [
        "id",
        "query",
        "author",
        "sources",
        "filters",
        "result_count",
        "created_at",
        "results",
    ]


def test_duplicate_search_clones_fields_under_a_new_id():
    import asyncio

    results = [{"title": "p0"}]
    inserts = []

    def handler(request):
        stmt = json.loads(request.content)["requests"][0]["stmt"]
        if stmt["sql"].startswith("SELECT id"):
            return httpx.Response(
                200,
                json=_pipeline(rows=[_search_row(results)], columns=_search_columns()),
            )
        inserts.append(stmt)
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    new_id = asyncio.run(cache.duplicate_search("old"))

    assert new_id is not None
    assert new_id != "old"
    assert len(inserts) == 1
    args = inserts[0]["args"]
    assert args[0]["value"] == new_id
    assert args[1]["value"] == "quantum (copy)"
    assert args[2]["value"] == "smith"
    assert json.loads(args[3]["value"]) == ["crossref"]
    assert json.loads(args[4]["value"]) == {"year": 2024}
    assert int(args[5]["value"]) == 1
    assert json.loads(args[7]["value"]) == results


def test_duplicate_search_returns_none_for_unknown_id():
    import asyncio

    def handler(request):
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    assert asyncio.run(cache.duplicate_search("missing")) is None


def test_export_workspace_returns_rows_with_results_newest_first():
    import asyncio

    older = [{"title": "old"}]
    newer = [{"title": "new"}]

    def handler(request):
        stmt = json.loads(request.content)["requests"][0]["stmt"]
        assert "ORDER BY created_at DESC" in stmt["sql"]
        return httpx.Response(
            200,
            json=_pipeline(
                rows=[_search_row(newer), _search_row(older)],
                columns=_search_columns(),
            ),
        )

    cache = TursoCache(_store(handler), ttl=60)
    rows = asyncio.run(cache.export_workspace(limit=5))

    assert [row["results"] for row in rows] == [newer, older]
    assert rows[0]["sources"] == ["crossref"]
    assert rows[0]["filters"] == {"year": 2024}


def test_import_workspace_inserts_every_entry():
    import asyncio

    inserts = []

    def handler(request):
        stmt = json.loads(request.content)["requests"][0]["stmt"]
        inserts.append(stmt)
        return httpx.Response(200, json=_pipeline())

    cache = TursoCache(_store(handler), ttl=60)
    archive = {
        "searches": [
            {"query": "quantum", "author": "smith", "results": [{"title": "p0"}]},
            {"query": "gravity", "result_count": 2, "results": [{"title": "p1"}]},
        ]
    }
    ids = asyncio.run(cache.import_workspace(archive))

    assert len(ids) == 2
    assert len(set(ids)) == 2
    assert len(inserts) == 2
    assert inserts[0]["args"][1]["value"] == "quantum"
    assert inserts[1]["args"][1]["value"] == "gravity"


def test_replay_search_returns_stored_results_as_stale():
    import asyncio

    results = [{"title": "p0"}]

    def handler(request):
        return httpx.Response(
            200,
            json=_pipeline(rows=[_search_row(results)], columns=_search_columns()),
        )

    cache = TursoCache(_store(handler), ttl=60)
    payload = asyncio.run(cache.replay_search("old"))

    assert payload["id"] == "old"
    assert payload["results"] == results
    assert payload["stale"] is True


def test_replay_search_returns_none_when_results_are_empty():
    import asyncio

    def handler(request):
        return httpx.Response(
            200,
            json=_pipeline(rows=[_search_row([])], columns=_search_columns()),
        )

    cache = TursoCache(_store(handler), ttl=60)
    assert asyncio.run(cache.replay_search("old")) is None


def test_info_reports_size_and_expiry_and_honours_prefix():
    import asyncio
    import time

    seen = []

    def handler(request):
        stmt = json.loads(request.content)["requests"][0]["stmt"]
        seen.append(stmt)
        return httpx.Response(
            200,
            json=_pipeline(
                rows=[
                    [
                        {"type": "text", "value": "abc:1"},
                        {"type": "integer", "value": "42"},
                        {"type": "float", "value": time.time() - 60},
                    ],
                    [
                        {"type": "text", "value": "abc:2"},
                        {"type": "integer", "value": "7"},
                        {"type": "float", "value": time.time() + 60},
                    ],
                ],
                columns=["key", "LENGTH(value)", "expires_at"],
            ),
        )

    cache = TursoCache(_store(handler), ttl=60)
    entries = asyncio.run(cache.info("abc", limit=10))

    assert "WHERE key LIKE ?" in seen[0]["sql"]
    assert seen[0]["args"] == [
        {"type": "text", "value": "abc%"},
        {"type": "integer", "value": "10"},
    ]
    assert entries[0]["key"] == "abc:1"
    assert entries[0]["size_bytes"] == 42
    assert entries[0]["expired"] is True
    assert entries[1]["expired"] is False


def test_list_searches_includes_size_and_age():
    import asyncio

    def handler(request):
        return httpx.Response(
            200,
            json=_pipeline(
                rows=[
                    _search_row([{"title": "p0"}])[:7]
                    + [{"type": "integer", "value": "12"}]
                ],
                columns=[
                    "id",
                    "query",
                    "author",
                    "sources",
                    "filters",
                    "result_count",
                    "created_at",
                    "size_bytes",
                ],
            ),
        )

    cache = TursoCache(_store(handler), ttl=60)
    rows = asyncio.run(cache.list_searches())

    assert rows[0]["size_bytes"] == 12
    assert "age_seconds" in rows[0]
    assert rows[0]["age_seconds"] > 0
