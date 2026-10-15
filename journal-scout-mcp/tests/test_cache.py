from journal_scout_mcp.cache import TTLCache, build_cache


def test_set_then_get_returns_value():
    cache = TTLCache(ttl=10, clock=lambda: 0.0)
    cache.set("k", {"v": 1})
    assert cache.get("k") == {"v": 1}


def test_entry_expires_after_ttl():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("k", 1)
    clock[0] = 9.9
    assert cache.get("k") == 1
    clock[0] = 10.0
    assert cache.get("k") is None
    assert len(cache) == 0


def test_missing_key_returns_none():
    assert TTLCache().get("absent") is None


def test_eviction_drops_soonest_expiring_when_full():
    clock = [0.0]
    cache = TTLCache(ttl=100, max_entries=2, clock=lambda: clock[0])
    cache.set("a", 1)
    clock[0] = 1.0
    cache.set("b", 2)
    clock[0] = 2.0
    cache.set("c", 3)  # over capacity -> evict the soonest-expiring ("a")
    assert len(cache) == 2
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_clear_empties_the_store():
    cache = TTLCache()
    cache.set("k", 1)
    cache.clear()
    assert len(cache) == 0


def test_build_cache_is_off_when_ttl_disabled():
    assert build_cache(None) is None
    assert build_cache(0) is None
    assert build_cache(-5) is None


def test_build_cache_is_on_when_ttl_positive():
    cache = build_cache(30)
    assert isinstance(cache, TTLCache)
    assert cache.ttl == 30
