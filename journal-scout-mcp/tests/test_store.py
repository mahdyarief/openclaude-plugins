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
