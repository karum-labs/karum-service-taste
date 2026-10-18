"""Metrics: status, latency, call and row counts (PLAN.md §7)."""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import QlooUpstreamError
from support import FakeTransport, make_settings, ok

SEED = ["32F867B9-E6DF-44C3-BCE4-40160C7ED5E4"]


def _place(entity_id: str, name: str) -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "name": name,
        "type": "urn:entity",
        "subtype": "urn:entity:place",
    }


async def test_metrics_track_calls_rows_and_latency() -> None:
    payload = {
        "results": {
            "entities": [
                _place("A29A1AE5-57F9-4C42-95CD-143C90F4B55A", "A"),
                _place("B29A1AE5-57F9-4C42-95CD-143C90F4B55A", "B"),
            ]
        }
    }
    transport = FakeTransport(ok(payload))
    client = QlooClient(make_settings(), transport=transport)
    await client.insights_places(SEED, location=(30.2672, -97.7431), radius_m=8000)
    entry = client.metrics.snapshot()["insights.place"]
    assert entry["calls"] == 1
    assert entry["errors"] == 0
    assert entry["rows"] == 2
    assert entry["error_codes"] == {}
    latency_avg = entry["latency_ms_avg"]
    latency_max = entry["latency_ms_max"]
    assert isinstance(latency_avg, float) and isinstance(latency_max, float)
    assert latency_max >= latency_avg >= 0


async def test_errors_count_per_endpoint_by_code() -> None:
    transport = FakeTransport(ok({}, status=500))
    client = QlooClient(make_settings(qloo_max_retries=0), transport=transport)
    with pytest.raises(QlooUpstreamError):
        await client.search("Aesop")
    entry = client.metrics.snapshot()["search"]
    assert entry["calls"] == 1
    assert entry["errors"] == 1
    assert entry["error_codes"] == {"upstream": 1}
    assert entry["rows"] == 0
