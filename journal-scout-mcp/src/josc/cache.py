"""Small TTL cache used to avoid re-hitting the same upstream query.

Provider responses for a given ``(provider, url, params)`` tuple are stable for
a while, so caching them cuts latency and — more importantly — conserves
metered quotas such as the Elsevier weekly limit. The cache is deliberately
dependency-free and clock-injectable so it can be unit-tested.
"""
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_TTL_SECONDS = 300.0
DEFAULT_MAX_ENTRIES = 1024


class TTLCache:
    """A minimal time-to-live cache with oldest-first eviction."""

    def __init__(
        self,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl = float(ttl)
        self._max_entries = max_entries
        self._clock = clock
        self._store: Dict[Any, Tuple[float, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._evictions = 0
        self._expired = 0

    @property
    def ttl(self) -> float:
        return self._ttl

    def get(self, key: Any) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            self._expired += 1
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: Any, value: Any) -> None:
        if self._max_entries and len(self._store) >= self._max_entries:
            self._evict()
        self._store[key] = (self._clock() + self._ttl, value)
        self._sets += 1

    def _evict(self) -> None:
        # Prefer dropping already-expired entries; otherwise drop the one
        # closest to expiring so fresh entries survive.
        now = self._clock()
        expired = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        if expired:
            for key in expired:
                del self._store[key]
            self._evictions += len(expired)
            return
        soonest = min(self._store, key=lambda k: self._store[k][0])
        del self._store[soonest]
        self._evictions += 1

    def clear(self, prefix: Optional[str] = None) -> int:
        # Counters are deliberately left intact so stats() keeps describing the
        # whole process lifetime rather than the current store contents.
        if prefix is None:
            removed = len(self._store)
            self._store.clear()
            return removed
        keys = [key for key in self._store if str(key).startswith(prefix)]
        for key in keys:
            del self._store[key]
        return len(keys)

    def __len__(self) -> int:
        return len(self._store)

    def stats(self) -> Dict[str, Any]:
        lookups = self._hits + self._misses
        return {
            "ttl": self._ttl,
            "entries": len(self._store),
            "max_entries": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "evictions": self._evictions,
            "expired": self._expired,
            "hit_rate": round(self._hits / lookups, 3) if lookups else 0.0,
        }

    def info(self, prefix: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Return read-only metadata for stored entries, soonest-expiring first."""
        now = self._clock()
        entries = []
        for key, (expires_at, value) in self._store.items():
            if prefix is not None and not str(key).startswith(prefix):
                continue
            ttl_remaining = round(expires_at - now, 1)
            try:
                size_bytes = len(json.dumps(value, default=str))
            except Exception:
                size_bytes = 0
            entries.append(
                (
                    expires_at,
                    {
                        "key": str(key),
                        "size_bytes": size_bytes,
                        "age_seconds": round(self._ttl - ttl_remaining, 1),
                        "ttl_remaining": ttl_remaining,
                        "expired": ttl_remaining <= 0,
                    },
                )
            )
        entries.sort(key=lambda item: item[0])
        return [entry for _, entry in entries[:limit]]


def build_cache(ttl: Optional[float]) -> Optional[TTLCache]:
    """Return a cache for ``ttl`` seconds, or ``None`` when caching is off."""
    if ttl is None or ttl <= 0:
        return None
    return TTLCache(ttl=ttl)
