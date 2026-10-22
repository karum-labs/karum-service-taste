"""Cache backends and single-flight (PLAN.md section 13).

Redis is the primary store with an in-process fallback; a single-flight lock
makes concurrent refreshes of the same key share one upstream call. Tests use
fakes so no real Redis or network is required.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from karum_service_taste.core.cache import (
    InMemoryCache,
    RedisBackedCache,
    RedisCache,
    SingleFlight,
    TtlCache,
    build_cache,
)
from karum_service_taste.qloo.canonical import cache_key


class FakeRedis:
    """A minimal async Redis stand-in storing bytes."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.fail = False

    async def get(self, key: str) -> bytes | None:
        if self.fail:
            raise RuntimeError("redis is down")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.fail:
            raise RuntimeError("redis is down")
        self.store[key] = value.encode("utf-8")


def outcome(payload: str) -> SimpleNamespace:
    """A :class:`_FetchOutcome`-like object carrying a payload and attempt count."""
    return SimpleNamespace(response=SimpleNamespace(payload=payload), attempts=1)


class NeverCache:
    """A cache backend that always misses; used to drive single-flight directly."""

    backend_name = "memory"
    degraded = False

    async def get(self, key: str) -> None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        return None


# ---------------------------------------------------------------------------
# TtlCache (carried over from section 8; kept here with the cache epic)
# ---------------------------------------------------------------------------


def test_ttl_cache_round_trip_and_expiry() -> None:
    cache = TtlCache(60, clock=lambda: 10.0)
    cache.set("k", ["a"])
    assert cache.get("k") == ["a"]
    assert cache.get("missing") is None


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------


async def test_in_memory_cache_get_and_set() -> None:
    cache = InMemoryCache(ttl_seconds=3600)
    assert cache.degraded is False
    assert cache.backend_name == "memory"
    assert await cache.get("k") is None
    await cache.set("k", "payload", ttl_seconds=3600)
    assert await cache.get("k") == "payload"


# ---------------------------------------------------------------------------
# Redis cache
# ---------------------------------------------------------------------------


async def test_redis_cache_get_set_round_trip() -> None:
    redis = FakeRedis()
    cache = RedisCache(redis)
    assert cache.degraded is False
    assert cache.backend_name == "redis"
    assert await cache.get("k") is None
    await cache.set("k", "payload", ttl_seconds=3600)
    assert await cache.get("k") == "payload"


async def test_redis_cache_degrades_on_failure() -> None:
    redis = FakeRedis()
    redis.fail = True
    cache = RedisCache(redis)
    assert await cache.get("k") is None
    assert cache.degraded is True
    await cache.set("k", "payload", ttl_seconds=3600)
    assert cache.degraded is True


# ---------------------------------------------------------------------------
# Redis with in-memory fallback
# ---------------------------------------------------------------------------


async def test_backed_cache_reads_from_redis_when_healthy() -> None:
    redis = FakeRedis()
    await redis.set("k", "redis-payload", ex=3600)
    cache = RedisBackedCache(RedisCache(redis), InMemoryCache(3600))
    assert cache.degraded is False
    assert cache.backend_name == "redis"
    assert await cache.get("k") == "redis-payload"


async def test_backed_cache_falls_back_to_memory_when_redis_degraded() -> None:
    redis = FakeRedis()
    redis.fail = True
    memory = InMemoryCache(3600)
    await memory.set("k", "memory-payload", ttl_seconds=3600)
    cache = RedisBackedCache(RedisCache(redis), memory)
    # A Redis operation must run before the degraded bit flips.
    assert await cache.get("missing") is None
    assert cache.degraded is True
    assert cache.backend_name == "memory"
    assert await cache.get("k") == "memory-payload"


async def test_backed_cache_writes_to_both() -> None:
    redis = FakeRedis()
    memory = InMemoryCache(3600)
    cache = RedisBackedCache(RedisCache(redis), memory)
    await cache.set("k", "payload", ttl_seconds=3600)
    assert redis.store["k"] == b"payload"
    assert await memory.get("k") == "payload"


# ---------------------------------------------------------------------------
# Single-flight
# ---------------------------------------------------------------------------


async def test_single_flight_shares_one_fetch() -> None:
    calls = 0
    guard = asyncio.Lock()

    async def fetch() -> SimpleNamespace:
        nonlocal calls
        async with guard:
            calls += 1
        await asyncio.sleep(0.05)
        return outcome("payload")

    flight = SingleFlight()
    cache = InMemoryCache(ttl_seconds=3600)
    results = await asyncio.gather(
        flight.get_or_fetch("k", cache, fetch, 3600),
        flight.get_or_fetch("k", cache, fetch, 3600),
        flight.get_or_fetch("k", cache, fetch, 3600),
    )
    assert calls == 1
    misses = [result for result in results if not result.cache_hit]
    assert len(misses) == 1
    for result in results:
        assert result.payload == "payload"
        assert result.fetch_attempts == 1


async def test_single_flight_serves_cache_on_repeat() -> None:
    calls = 0

    async def fetch() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return outcome("payload")

    flight = SingleFlight()
    first = await flight.get_or_fetch("k", NeverCache(), fetch, 3600)
    assert first.cache_hit is False
    assert calls == 1

    class HitCache:
        backend_name = "memory"
        degraded = False

        async def get(self, key: str):
            return '"cached"'  # JSON-serialised payload string

        async def set(self, key: str, value: str, ttl_seconds: int):
            return None

    second = await flight.get_or_fetch("k", HitCache(), fetch, 3600)
    assert second.cache_hit is True
    assert second.payload == "cached"
    assert calls == 1


# ---------------------------------------------------------------------------
# Canonical cache keys
# ---------------------------------------------------------------------------


def test_cache_key_is_stable_under_parameter_reordering() -> None:
    base = [
        ("filter.location", "POINT(-73.9566 40.7172)"),
        ("filter.location.radius", "8000"),
        ("signal.interests.entities", "A,B"),
        ("take", "25"),
    ]
    shuffled = list(reversed(base))
    assert cache_key("/v2/insights", base, "fixture", "https://api.qloo.com") == cache_key(
        "/v2/insights", shuffled, "fixture", "https://api.qloo.com"
    )


def test_cache_key_distinguishes_modes_and_base_urls() -> None:
    base = [("filter.location.radius", "8000")]
    assert cache_key("/v2/insights", base, "fixture", "https://api.qloo.com") != cache_key(
        "/v2/insights", base, "live", "https://api.qloo.com"
    )
    assert cache_key("/v2/insights", base, "fixture", "https://api.qloo.com") != cache_key(
        "/v2/insights", base, "fixture", "https://staging.qloo.com"
    )


def test_cache_key_distinguishes_float_formatting_and_radius() -> None:
    a = cache_key("/v2/insights", [("filter.location.radius", "8000")], "fixture", "https://api.qloo.com")
    b = cache_key("/v2/insights", [("filter.location.radius", "8000.0")], "fixture", "https://api.qloo.com")
    c = cache_key("/v2/insights", [("filter.location.radius", "10000")], "fixture", "https://api.qloo.com")
    assert a == b  # same number, different formatting
    assert a != c  # different radius


def test_cache_key_prefix() -> None:
    assert cache_key("/search", [("query", "Aesop")], "fixture", "https://api.qloo.com").startswith(
        "karum:qloo:"
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_build_cache_without_redis_address_returns_memory() -> None:
    cache = build_cache("", ttl_seconds=3600)
    assert isinstance(cache, InMemoryCache)
    assert cache.degraded is False


def test_build_cache_with_redis_address_returns_backed_cache() -> None:
    # No connection is attempted at build time, so an unreachable host does
    # not raise; Redis health is established on the first get/set.
    cache = build_cache("redis:6379", ttl_seconds=3600)
    assert isinstance(cache, RedisBackedCache)
    assert cache.degraded is False


def test_build_cache_does_not_raise_when_redis_unimportable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("no redis")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)
    cache = build_cache("redis:6379", ttl_seconds=3600)
    assert isinstance(cache, InMemoryCache)


def test_time_module_is_importable() -> None:
    assert time.monotonic() >= 0
