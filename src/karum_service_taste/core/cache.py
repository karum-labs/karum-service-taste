"""Cache backends for Qloo responses (PLAN.md section 13).

Qloo responses are cached under a canonical hash of the request parameters
with a 24h TTL. Redis is the primary store; when Redis is down the service
falls back to an in-process cache and flips the degraded health bit. A
single-flight lock makes concurrent refreshes of the same key share one
upstream call so a burst cannot stampede Qloo.

The original short-TTL store used by seed resolution
(:class:`TtlCache`, PLAN.md section 8) lives here too and is now the
in-memory fallback behind the Redis-backed cache.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """A key/value store for serialized Qloo payloads.

    ``get`` returns the cached payload string or ``None`` on a miss;
    ``set`` stores ``value`` for ``ttl_seconds``. ``degraded`` is True when
    the store cannot be trusted (e.g. Redis is unreachable). ``backend_name``
    is a human label for health reporting.
    """

    degraded: bool
    backend_name: str

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


# ---------------------------------------------------------------------------
# In-process TTL cache (the section-8 store, now the in-memory fallback)
# ---------------------------------------------------------------------------


class TtlCache:
    """Keyed TTL store.

    ``None`` means "no live entry": a cached empty list (a negative lookup)
    comes back as ``[]``, so callers can cache misses deliberately.
    """

    def __init__(
        self,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Return the live value for ``key``, or ``None`` when absent/expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` for one TTL window."""
        self._entries[key] = (self._clock() + self._ttl_seconds, value)

    def __len__(self) -> int:
        """Entries retained, expired ones included until next touched."""
        return len(self._entries)


class InMemoryCache:
    """In-process cache backed by :class:`TtlCache`; never degraded."""

    backend_name = "memory"
    degraded = False

    def __init__(self, ttl_seconds: int) -> None:
        self._cache = TtlCache(float(ttl_seconds))

    async def get(self, key: str) -> str | None:
        value = self._cache.get(key)
        return None if value is None else str(value)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store ``value``; the per-call TTL matches the construction TTL."""
        self._cache.set(key, value)


# ---------------------------------------------------------------------------
# Redis cache
# ---------------------------------------------------------------------------


class RedisCache:
    """Redis-backed store; flips ``degraded`` when Redis cannot be reached."""

    backend_name = "redis"

    def __init__(self, client: Any) -> None:
        self._client = client
        self.degraded = False

    async def get(self, key: str) -> str | None:
        try:
            raw = await self._client.get(key)
        except Exception:  # noqa: BLE001 - any Redis failure degrades gracefully
            self.degraded = True
            return None
        self.degraded = False
        return None if raw is None else raw.decode("utf-8")

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            await self._client.set(key, value, ex=ttl_seconds)
        except Exception:  # noqa: BLE001 - any Redis failure degrades gracefully
            self.degraded = True
        else:
            self.degraded = False


# ---------------------------------------------------------------------------
# Redis primary with an in-memory fallback
# ---------------------------------------------------------------------------


class RedisBackedCache:
    """Redis first, in-process second; ``degraded`` tracks Redis health."""

    def __init__(self, redis: RedisCache, memory: InMemoryCache) -> None:
        self._redis = redis
        self._memory = memory

    @property
    def degraded(self) -> bool:
        return self._redis.degraded

    @property
    def backend_name(self) -> str:
        return "memory" if self.degraded else "redis"

    async def get(self, key: str) -> str | None:
        if not self.degraded:
            value = await self._redis.get(key)
            if value is not None:
                return value
        return await self._memory.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if not self.degraded:
            await self._redis.set(key, value, ttl_seconds)
        await self._memory.set(key, value, ttl_seconds)


# ---------------------------------------------------------------------------
# Single-flight: one upstream refresh per key at a time
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleFlightResult:
    """Outcome of :meth:`SingleFlight.get_or_fetch`.

    Attributes:
        payload: the deserialized payload object, ready to be parsed.
        cache_hit: True when the payload came from the cache.
        fetch_attempts: how many upstream attempts the fetch took (1 on a hit).
        outcome: the raw fetch outcome on a miss (None on a hit); carries the
            transport response so the caller can build the call record.
    """

    payload: Any
    cache_hit: bool
    fetch_attempts: int
    outcome: Any | None = None


class SingleFlight:
    """Ensures concurrent refreshes of the same key share one upstream call.

    Callers racing on the same key serialize on a per-key lock: the first
    fetches from upstream and populates the cache, the rest are served the
    cached result instead of repeating the call. Payloads are serialized to
    JSON before being handed to the cache backend.
    """

    def __init__(self) -> None:
        self._locks: dict[str, Any] = {}

    async def get_or_fetch(
        self,
        key: str,
        cache: CacheBackend,
        fetch: Callable[[], Any],
        ttl_seconds: int,
    ) -> SingleFlightResult:
        """Return the cached payload, or run ``fetch`` once and store it."""
        import asyncio

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = await cache.get(key)
            if cached is not None:
                return SingleFlightResult(json.loads(cached), True, 1, None)
            outcome = await fetch()
            await cache.set(key, json.dumps(outcome.response.payload), ttl_seconds)
            return SingleFlightResult(outcome.response.payload, False, outcome.attempts, outcome)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _build_redis_client(redis_addr: str) -> Any | None:
    """Build a Redis client, or return None when Redis is not configured."""
    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        return None
    if not redis_addr:
        return None
    host, _, port = redis_addr.partition(":")
    return redis.asyncio.Redis(
        host=host or "localhost",
        port=int(port) if port else 6379,
    )


def build_cache(redis_addr: str, *, ttl_seconds: int) -> CacheBackend:
    """Build the cache for the service: Redis primary, memory fallback.

    When Redis is not configured (or unavailable) the store degrades to the
    in-process cache; the health endpoint reports ``degraded`` only when Redis
    was configured but cannot be reached.
    """
    memory = InMemoryCache(ttl_seconds)
    client = _build_redis_client(redis_addr)
    if client is not None:
        return RedisBackedCache(RedisCache(client), memory)
    return memory
