"""The short-TTL cache used by seed resolution (PLAN.md §8)."""

from __future__ import annotations

import pytest

from karum_service_taste.core.cache import TtlCache
from support import SleepingClock


def test_set_and_get_round_trips_values() -> None:
    cache: TtlCache[list[str]] = TtlCache(60)
    cache.set("k", ["a"])
    assert cache.get("k") == ["a"]
    assert cache.get("missing") is None


def test_negative_lookups_cache_like_any_value() -> None:
    cache: TtlCache[list[str]] = TtlCache(60)
    cache.set("k", [])
    assert cache.get("k") == []


def test_entries_expire_on_the_clock() -> None:
    virtual = SleepingClock()
    cache: TtlCache[list[str]] = TtlCache(60, clock=virtual.clock)
    cache.set("k", ["a"])
    virtual.now = 59.9
    assert cache.get("k") == ["a"]
    virtual.now = 60.0
    assert cache.get("k") is None
    assert len(cache) == 0


def test_non_positive_ttl_is_rejected() -> None:
    with pytest.raises(ValueError):
        TtlCache(0)
