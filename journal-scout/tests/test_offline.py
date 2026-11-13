"""Tests for offline mode, TursoCache telemetry, and /api/health store stats."""

from josc.store import TursoCache


class FakeCache:
    """Minimal TursoCache stand-in driven by a dict of key -> payload."""

    def __init__(self, returns=None):
        self.returns = returns
        self.gets = 0
        self.sets = 0

    async def get(self, key):
        self.gets += 1
        return self.returns

    async def set(self, key, value):
        self.sets += 1


class FakeTurso:
    """Stand-in TursoStore: returns canned rows and records every statement."""

    def __init__(self):
        self.calls = []
        self.get_rows = []

    async def execute(self, sql, args=None):
        self.calls.append((sql, args))
        if sql.startswith("SELECT value, expires_at"):
            return (["value", "expires_at"], list(self.get_rows))
        if sql.startswith("SELECT COUNT(*)"):
            return (["count", "expired"], [[7, 2]])
        return (["affected_row_count"], [[0]])


def _client(monkeypatch, store):
    from starlette.testclient import TestClient

    import josc.api as api

    monkeypatch.setitem(api._state, "store", store)
    monkeypatch.setitem(api._state, "providers", [])
    return api, TestClient(api.app)


def test_offline_without_store_returns_503(monkeypatch):
    _, client = _client(monkeypatch, None)
    response = client.get("/api/search", params={"query": "x", "offline": "true"})
    assert response.status_code == 503
    body = response.json()
    assert body["offline"] is True


def test_offline_cache_hit_marks_stale(monkeypatch):
    cached = {"results": [], "errors": {}, "counts": {}}
    _, client = _client(monkeypatch, FakeCache(cached))

    import josc.api as api

    async def boom(*args, **kwargs):
        raise AssertionError("offline mode must not reach the network")

    monkeypatch.setattr(api.aggregator, "search_all", boom)
    response = client.get("/api/search", params={"query": "x", "offline": "true"})
    assert response.status_code == 200
    body = response.json()
    assert body["stale"] is True
    assert body["results"] == []


def test_offline_cache_miss_returns_503(monkeypatch):
    _, client = _client(monkeypatch, FakeCache(None))
    response = client.get("/api/search", params={"query": "x", "offline": "true"})
    assert response.status_code == 503
    assert response.json()["offline"] is True


def test_online_still_calls_factory(monkeypatch):
    calls = {"n": 0}

    import josc.api as api

    async def fake_search(providers, query, **kwargs):
        calls["n"] += 1
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    store = FakeCache(None)
    _, client = _client(monkeypatch, store)

    response = client.get("/api/search", params={"query": "x"})
    assert response.status_code == 200
    assert calls["n"] == 1
    assert "stale" not in response.json()
    assert store.gets == 1
    assert store.sets == 1


async def test_turso_stats_counts():
    turso = FakeTurso()
    cache = TursoCache(turso, ttl=60)

    turso.get_rows = [['{"a": 1}', 9999999999.0]]
    assert await cache.get(("k",)) == {"a": 1}

    turso.get_rows = []
    assert await cache.get(("missing",)) is None

    await cache.set(("k",), {"a": 1})

    stats = await cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["sets"] == 1
    assert stats["entries"] == 7
    assert stats["expired"] == 2
    assert stats["hit_rate"] == 0.5
    assert stats["backend"] == "turso"
    assert stats["ttl"] == 60.0


def test_health_exposes_store_null_when_unset(monkeypatch):
    _, client = _client(monkeypatch, None)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert "store" in body
    assert body["store"] is None


def test_health_reports_store_stats(monkeypatch):
    class StatsCache(FakeCache):
        async def stats(self):
            return {"backend": "turso", "hits": 3, "misses": 1}

    _, client = _client(monkeypatch, StatsCache())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["store"] == {"backend": "turso", "hits": 3, "misses": 1}
