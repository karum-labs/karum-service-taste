"""Retries, backoff, rate-limit holds, and failure mapping (PLAN.md §7)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import (
    ErrorCode,
    QlooRateLimitedError,
    QlooTransportError,
    QlooUpstreamError,
    QlooValidationError,
)
from support import FakeTransport, SleepingClock, make_settings, ok


def _client(
    transport: FakeTransport,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    **overrides: object,
) -> QlooClient:
    return QlooClient(make_settings(**overrides), transport=transport, sleep=sleep)


async def test_5xx_is_retried_then_succeeds() -> None:
    transport = FakeTransport(ok({}, status=500), ok({"results": []}))
    response = await _client(transport).search("Aesop")
    assert response.call is not None
    assert response.call.attempts == 2
    assert len(transport.requests) == 2


async def test_retry_sleeps_exponential_backoff() -> None:
    virtual = SleepingClock()
    transport = FakeTransport(ok({}, status=503), ok({}, status=503), ok({"results": []}))
    await _client(transport, sleep=virtual.sleep, qloo_backoff_base_seconds=0.5).search("Aesop")
    assert virtual.slept == [0.5, 1.0]


async def test_exhausted_retries_raise_upstream() -> None:
    transport = FakeTransport(*[ok({}, status=500)] * 4)
    with pytest.raises(QlooUpstreamError) as excinfo:
        await _client(transport).search("Aesop")
    assert excinfo.value.error_code is ErrorCode.UPSTREAM
    assert excinfo.value.status == 500
    assert excinfo.value.endpoint == "search"
    assert len(transport.requests) == 4


async def test_timeout_is_retried() -> None:
    transport = FakeTransport(QlooTransportError("timeout"), ok({"results": []}))
    response = await _client(transport).search("Aesop")
    assert response.call is not None
    assert response.call.attempts == 2


async def test_exhausted_timeout_maps_to_upstream() -> None:
    transport = FakeTransport(QlooTransportError("timeout"))
    with pytest.raises(QlooTransportError) as excinfo:
        await _client(transport, qloo_max_retries=0).search("Aesop")
    assert excinfo.value.error_code is ErrorCode.UPSTREAM


async def test_400_is_not_retried() -> None:
    transport = FakeTransport(ok({"error": "bad"}, status=400))
    with pytest.raises(QlooValidationError) as excinfo:
        await _client(transport).search("Aesop")
    assert excinfo.value.status == 400
    assert len(transport.requests) == 1


async def test_401_is_upstream_not_validation() -> None:
    transport = FakeTransport(ok({"error": "unauthorized"}, status=401))
    with pytest.raises(QlooUpstreamError) as excinfo:
        await _client(transport).search("Aesop")
    assert excinfo.value.error_code is ErrorCode.UPSTREAM


async def test_429_honours_retry_after_then_succeeds() -> None:
    virtual = SleepingClock()
    transport = FakeTransport(
        ok({"error": "slow down"}, status=429, headers={"Retry-After": "2"}),
        ok({"results": []}),
    )
    response = await _client(transport, sleep=virtual.sleep, qloo_backoff_base_seconds=0.1).search(
        "Aesop"
    )
    assert virtual.slept == [2.0]
    assert response.call is not None
    assert response.call.attempts == 2


async def test_429_without_retry_after_uses_the_second_reset() -> None:
    virtual = SleepingClock()
    transport = FakeTransport(
        ok({}, status=429, headers={"X-Second-RateLimit-Reset": "1.5"}),
        ok({"results": []}),
    )
    await _client(transport, sleep=virtual.sleep).search("Aesop")
    assert virtual.slept == [1.5]


async def test_exhausted_429_raises_rate_limited() -> None:
    transport = FakeTransport(ok({}, status=429, headers={"Retry-After": "0"}))
    with pytest.raises(QlooRateLimitedError) as excinfo:
        await _client(transport, qloo_max_retries=0).search("Aesop")
    assert excinfo.value.error_code is ErrorCode.RATE_LIMITED


async def test_second_budget_exhausted_holds_the_next_call() -> None:
    virtual = SleepingClock()
    transport = FakeTransport(
        ok(
            {"results": []},
            headers={"X-Second-RateLimit-Remaining": "0", "X-Second-RateLimit-Reset": "1"},
        ),
        ok({"results": []}),
    )
    client = _client(transport, sleep=virtual.sleep)
    await client.search("Aesop")
    await client.search("Ilegal")
    # The hold runs on the pacer's wall clock, so allow a little drift.
    assert len(virtual.slept) == 1
    assert virtual.slept[0] == pytest.approx(1.0, rel=0.1)


async def test_month_budget_exhausted_refuses_without_calling() -> None:
    transport = FakeTransport(
        ok(
            {"results": []},
            headers={"X-Month-RateLimit-Remaining": "0", "X-Month-RateLimit-Reset": "1000"},
        )
    )
    client = _client(transport)
    await client.search("Aesop")  # learns the month state from the headers
    with pytest.raises(QlooRateLimitedError) as excinfo:
        await client.search("Ilegal")
    assert len(transport.requests) == 1
    assert excinfo.value.retry_after == 1000


async def test_metrics_count_successes_and_failures() -> None:
    transport = FakeTransport(ok({"results": []}), ok({}, status=500))
    client = _client(transport, qloo_max_retries=0)
    await client.search("Aesop")
    with pytest.raises(QlooUpstreamError):
        await client.search("Ilegal")
    snapshot = client.metrics.snapshot()
    assert snapshot["search"]["calls"] == 2
    assert snapshot["search"]["errors"] == 1
    assert snapshot["search"]["error_codes"] == {"upstream": 1}
