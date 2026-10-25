from josc.cache import TTLCache, build_cache


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


def test_fresh_cache_reports_zero_activity():
    stats = TTLCache(ttl=10).stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["hit_rate"] == 0.0


def test_live_get_counts_one_hit():
    cache = TTLCache(ttl=10, clock=lambda: 0.0)
    cache.set("k", 1)
    assert cache.get("k") == 1
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["sets"] == 1
    assert stats["hit_rate"] == 1.0


def test_absent_key_counts_one_miss():
    cache = TTLCache(ttl=10, clock=lambda: 0.0)
    assert cache.get("absent") is None
    stats = cache.stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0


def test_expired_get_counts_miss_and_expiration():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("k", 1)
    clock[0] = 10.0
    assert cache.get("k") is None
    stats = cache.stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0
    assert stats["expired"] == 1


def test_eviction_increments_eviction_counter():
    clock = [0.0]
    cache = TTLCache(ttl=100, max_entries=1, clock=lambda: clock[0])
    cache.set("a", 1)
    clock[0] = 1.0
    cache.set("b", 2)  # over capacity -> "a" evicted
    stats = cache.stats()
    assert stats["evictions"] == 1
    assert stats["entries"] == 1


def test_stats_values_are_json_serializable_primitives():
    import json

    clock = [0.0]
    cache = TTLCache(ttl=10, max_entries=8, clock=lambda: clock[0])
    cache.set("a", 1)
    clock[0] = 20.0
    cache.get("a")  # expired: miss + expiration
    cache.get("missing")  # miss
    stats = cache.stats()
    encoded = json.dumps(stats)
    decoded = json.loads(encoded)
    assert decoded == stats
    for value in stats.values():
        assert isinstance(value, (int, float, str, bool, type(None)))


def test_clear_returns_count_and_empties_store():
    cache = TTLCache()
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.clear() == 2
    assert len(cache) == 0
    assert cache.stats()["entries"] == 0


def test_clear_with_prefix_removes_only_matching_keys():
    cache = TTLCache()
    cache.set("prefix:a", 1)
    cache.set("prefix:b", 2)
    cache.set("other", 3)
    assert cache.clear("prefix:") == 2
    assert len(cache) == 1
    assert cache.get("other") == 3


def test_clear_leaves_counters_untouched():
    clock = [0.0]
    cache = TTLCache(ttl=100, max_entries=1, clock=lambda: clock[0])
    cache.set("a", 1)
    cache.get("a")
    cache.get("missing")
    clock[0] = 1.0
    cache.set("b", 2)  # eviction
    before = cache.stats()
    cache.clear()
    after = cache.stats()
    assert after["entries"] == 0
    for name in ("hits", "misses", "sets", "evictions", "expired"):
        assert after[name] == before[name]


def test_info_orders_by_soonest_expiry_and_has_all_keys():
    clock = [0.0]
    cache = TTLCache(ttl=100, clock=lambda: clock[0])
    cache.set("later", 1)
    clock[0] = 10.0
    cache.set("sooner", 2)  # set later -> expires later, so "later" is soonest
    info = cache.info()
    assert len(info) == 2
    assert [entry["key"] for entry in info] == ["later", "sooner"]
    for entry in info:
        assert set(entry) == {
            "key",
            "size_bytes",
            "age_seconds",
            "ttl_remaining",
            "expired",
        }


def test_info_size_bytes_positive_for_dict_and_live_entry():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("k", {"a": 1, "b": 2})
    entry = cache.info()[0]
    assert entry["size_bytes"] > 0
    assert entry["expired"] is False


def test_info_reports_expired_after_ttl_without_get():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("k", 1)
    clock[0] = 15.0
    entry = cache.info()[0]
    assert entry["expired"] is True
    assert entry["ttl_remaining"] <= 0


def test_info_prefix_filters_keys():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("prefix:a", 1)
    cache.set("prefix:b", 2)
    cache.set("other", 3)
    info = cache.info(prefix="prefix:")
    assert len(info) == 2
    assert {entry["key"] for entry in info} == {"prefix:a", "prefix:b"}


def test_info_leaves_stats_counters_untouched():
    clock = [0.0]
    cache = TTLCache(ttl=10, clock=lambda: clock[0])
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")
    cache.get("missing")
    before = cache.stats()
    cache.info()
    after = cache.stats()
    for name in ("hits", "misses", "sets", "evictions", "expired", "entries"):
        assert after[name] == before[name]
