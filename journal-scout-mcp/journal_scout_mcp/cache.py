"""Small TTL cache used to avoid re-hitting the same upstream query.

Provider responses for a given ``(provider, url, params)`` tuple are stable for
a while, so caching them cuts latency and — more importantly — conserves
metered quotas such as the Elsevier weekly limit. The cache is deliberately
dependency-free and clock-injectable so it can be unit-tested.
"""
import time
from typing import Any, Callable, Dict, Optional, Tuple

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

    @property
    def ttl(self) -> float:
        return self._ttl

    def get(self, key: Any) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        if self._max_entries and len(self._store) >= self._max_entries:
            self._evict()
        self._store[key] = (self._clock() + self._ttl, value)

    def _evict(self) -> None:
        # Prefer dropping already-expired entries; otherwise drop the one
        # closest to expiring so fresh entries survive.
        now = self._clock()
        expired = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        if expired:
            for key in expired:
                del self._store[key]
            return
        soonest = min(self._store, key=lambda k: self._store[k][0])
        del self._store[soonest]

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


def build_cache(ttl: Optional[float]) -> Optional[TTLCache]:
    """Return a cache for ``ttl`` seconds, or ``None`` when caching is off."""
    if ttl is None or ttl <= 0:
        return None
    return TTLCache(ttl=ttl)
