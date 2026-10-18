"""QlooClient cache integration (PLAN.md section 13).

Cached requests are served without touching the transport; eval bypass never
stores results back into the cache.
"""

from __future__ import annotations

import pytest

from karum_service_taste.core.cache import InMemoryCache
from karum_service_taste.qloo.client import QlooClient
from support import FakeTransport, make_settings, ok


def _client(transport: FakeTransport, cache=None, eval_bypass: bool = False) -> QlooClient:
    return QlooClient(
        make_settings(),
        transport=transport,
        cache=cache,
        eval_bypass=eval_bypass,
    )


async def test_first_call_hits_transport_and_stores_in_cache() -> None:
    transport = FakeTransport(ok({"results": {"tags": []}}))
    cache = InMemoryCache(ttl_seconds=3600)
    client = _client(transport, cache=cache)

    response = await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    assert len(transport.requests) == 1
    assert response.call is not None and response.call.cache_hit is False

    # Identical request: served from cache, transport untouched.
    cached = await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    assert len(transport.requests) == 1
    assert cached.call is not None and cached.call.cache_hit is True


async def test_different_parameters_are_cache_misses() -> None:
    transport = FakeTransport(ok({"results": {"tags": []}}), ok({"results": {"tags": []}}))
    cache = InMemoryCache(ttl_seconds=3600)
    client = _client(transport, cache=cache)

    await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    await client.tags("cafe", tag_types=["urn:tag:genre"], take=15)
    assert len(transport.requests) == 2


async def test_eval_bypass_never_stores_or_reads_cache() -> None:
    transport = FakeTransport(
        ok({"results": {"tags": []}}),
        ok({"results": {"tags": []}}),
        ok({"results": {"tags": []}}),
    )
    cache = InMemoryCache(ttl_seconds=3600)
    client = _client(transport, cache=cache, eval_bypass=True)

    await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    first = await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    # All three calls went upstream; none was served from the cache.
    assert len(transport.requests) == 3
    assert first.call is not None and first.call.cache_hit is False


async def test_cache_hit_returns_identical_rows() -> None:
    payload = {
        "results": {
            "tags": [
                {"id": "urn:tag:genre:place:restaurant:bar", "name": "Bar", "type": "urn:tag:genre"}
            ]
        }
    }
    transport = FakeTransport(ok(payload))
    cache = InMemoryCache(ttl_seconds=3600)
    client = _client(transport, cache=cache)

    first = await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    second = await client.tags("bar", tag_types=["urn:tag:genre"], take=15)
    assert [tag.id for tag in first.rows] == [tag.id for tag in second.rows]
    assert second.call is not None and second.call.cache_hit is True


@pytest.mark.asyncio
async def test_health_reports_cache_backend_and_degraded_bit() -> None:
    from fastapi.testclient import TestClient

    from karum_service_taste.main import create_app

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["cache"]["backend"] in {"redis", "memory"}
    assert isinstance(body["cache"]["degraded"], bool)
