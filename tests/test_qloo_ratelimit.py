"""Rate-limit parsing and pacing (PLAN.md §7)."""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.ratelimit import Pacer, RateLimitSnapshot
from support import SleepingClock

HEADERS = {
    "X-Second-RateLimit-Limit": "5",
    "X-Second-RateLimit-Remaining": "4",
    "X-Second-RateLimit-Reset": "1",
    "X-Month-RateLimit-Limit": "10000",
    "X-Month-RateLimit-Remaining": "9855",
    "X-Month-RateLimit-Reset": "2433636.15",
}


def test_snapshot_parses_the_observed_headers() -> None:
    snapshot = RateLimitSnapshot.from_headers(HEADERS)
    assert snapshot is not None
    assert snapshot.second_limit == 5
    assert snapshot.second_remaining == 4
    assert snapshot.second_reset == 1
    assert snapshot.month_limit == 10000
    assert snapshot.month_remaining == 9855
    assert snapshot.month_reset == pytest.approx(2433636.15)


def test_snapshot_header_names_are_case_insensitive() -> None:
    lowercased = {key.lower(): value for key, value in HEADERS.items()}
    assert RateLimitSnapshot.from_headers(lowercased) == RateLimitSnapshot.from_headers(HEADERS)


def test_snapshot_is_none_without_the_headers() -> None:
    assert RateLimitSnapshot.from_headers({"Date": "Sun, 18 Oct 2026"}) is None


def test_snapshot_treats_unparseable_values_as_absent() -> None:
    assert RateLimitSnapshot.from_headers({"X-Second-RateLimit-Remaining": "many"}) is None
    snapshot = RateLimitSnapshot.from_headers(
        {"X-Second-RateLimit-Remaining": "many", "X-Second-RateLimit-Limit": "5"}
    )
    assert snapshot is not None
    assert snapshot.second_remaining is None
    assert snapshot.second_limit == 5


async def test_pacer_spaces_calls_by_the_minimum_interval() -> None:
    virtual = SleepingClock()
    pacer = Pacer(0.5, clock=virtual.clock, sleep=virtual.sleep)

    await pacer.wait()
    assert virtual.slept == []

    await pacer.wait()
    assert virtual.slept == [0.5]


async def test_pacer_hold_blocks_the_next_call() -> None:
    virtual = SleepingClock()
    pacer = Pacer(0.0, clock=virtual.clock, sleep=virtual.sleep)

    await pacer.wait()
    await pacer.hold(5)
    await pacer.wait()

    assert virtual.slept == [5]


async def test_pacer_ignores_non_positive_holds() -> None:
    virtual = SleepingClock()
    pacer = Pacer(0.0, clock=virtual.clock, sleep=virtual.sleep)
    await pacer.hold(0)
    await pacer.wait()
    assert virtual.slept == []
