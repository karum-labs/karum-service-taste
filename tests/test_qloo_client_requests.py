"""Request building, response parsing, and validation for every endpoint."""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import QlooPayloadError, QlooValidationError
from karum_service_taste.qloo.fixtures import FixturePack
from support import FakeTransport, make_settings, ok

SEED = ["32F867B9-E6DF-44C3-BCE4-40160C7ED5E4", "41C4BB40-E667-416F-9541-63FD7E7FFFF5"]


def _client(transport: FakeTransport, **overrides: object) -> QlooClient:
    return QlooClient(make_settings(**overrides), transport=transport)


async def test_search_builds_the_recorded_shape() -> None:
    transport = FakeTransport(ok({"results": []}))
    await _client(transport).search(
        "Leopold Cafe",
        types=["urn:entity:place"],
        take=5,
        page=1,
        location=(18.9221, 72.8317),
        radius_miles=5.0,
        sort_by="distance",
    )
    path, params = transport.requests[0]
    assert path == "/search"
    assert dict(params) == {
        "query": "Leopold Cafe",
        "types": "urn:entity:place",
        "take": "5",
        "page": "1",
        "filter.location": "18.9221,72.8317",
        "filter.radius": "5",
        "sort_by": "distance",
    }


async def test_search_omits_unset_parameters() -> None:
    transport = FakeTransport(ok({"results": []}))
    await _client(transport).search("Aesop", types=["urn:entity:brand"], take=5)
    _, params = transport.requests[0]
    assert dict(params) == {"query": "Aesop", "types": "urn:entity:brand", "take": "5"}


async def test_search_rejects_an_empty_query_without_calling() -> None:
    transport = FakeTransport(ok({"results": []}))
    with pytest.raises(QlooValidationError):
        await _client(transport).search("   ")
    assert transport.requests == []


async def test_tags_builds_the_recorded_shape() -> None:
    transport = FakeTransport(ok({"results": {"tags": []}}))
    await _client(transport).tags("bar", tag_types=["urn:tag:genre"], take=15)
    path, params = transport.requests[0]
    assert path == "/v2/tags"
    assert dict(params) == {
        "filter.query": "bar",
        "filter.tag.types": "urn:tag:genre",
        "take": "15",
    }


async def test_insights_places_builds_every_recorded_parameter() -> None:
    transport = FakeTransport(ok({"results": {"entities": []}}))
    await _client(transport).insights_places(
        SEED,
        location=(30.2672, -97.7431),
        radius_m=8000,
        category_tags=["urn:tag:genre:place:restaurant:bar"],
        interest_tags=["urn:tag:genre:place:restaurant"],
        results_entities=["314D0217-CAF0-4758-AB13-6C5CEB355431"],
        take=25,
    )
    _, params = transport.requests[0]
    assert dict(params) == {
        "filter.type": "urn:entity:place",
        "signal.interests.entities": ",".join(SEED),
        "filter.location": "POINT(-97.7431 30.2672)",
        "filter.location.radius": "8000",
        "filter.tags": "urn:tag:genre:place:restaurant:bar",
        "signal.interests.tags": "urn:tag:genre:place:restaurant",
        "filter.results.entities": "314D0217-CAF0-4758-AB13-6C5CEB355431",
        "take": "25",
        "feature.explainability": "true",
    }


async def test_insights_places_explainability_off_omits_the_flag() -> None:
    transport = FakeTransport(ok({"results": {"entities": []}}))
    await _client(transport).insights_places(
        SEED, location=(30.2672, -97.7431), radius_m=8000, take=50, explainability=False
    )
    _, params = transport.requests[0]
    assert "feature.explainability" not in dict(params)
    assert dict(params)["take"] == "50"


async def test_heatmap_and_locality_share_the_endpoint() -> None:
    transport = FakeTransport(
        ok({"results": {"heatmap": []}}),
        ok({"results": {"entities": []}}),
    )
    client = _client(transport)
    await client.insights_heatmap(
        SEED, location=(40.7172, -73.9566), radius_m=10000, boundary="urn:geohash", take=50
    )
    await client.insights_localities(SEED, location=(40.7172, -73.9566), radius_m=10000)
    first = dict(transport.requests[0][1])
    second = dict(transport.requests[1][1])
    assert first == {
        "filter.type": "urn:heatmap",
        "signal.interests.entities": ",".join(SEED),
        "filter.location": "POINT(-73.9566 40.7172)",
        "filter.location.radius": "10000",
        "take": "50",
        "output.heatmap.boundary": "urn:geohash",
    }
    assert second["output.heatmap.boundary"] == "urn:entity:locality"
    assert transport.requests[0][0] == transport.requests[1][0] == "/v2/insights"


async def test_insights_demographics_optional_parameters() -> None:
    transport = FakeTransport(
        ok({"results": {"demographics": []}}),
        ok({"results": {"demographics": []}}),
    )
    client = _client(transport)
    await client.insights_demographics(SEED)
    await client.insights_demographics(
        SEED, results_entities=["AF59EF83-C53B-45AB-A980-D5EEECB3A8F0"], take=25
    )
    assert dict(transport.requests[0][1]) == {
        "filter.type": "urn:demographics",
        "signal.interests.entities": ",".join(SEED),
    }
    second = dict(transport.requests[1][1])
    assert second["filter.results.entities"] == "AF59EF83-C53B-45AB-A980-D5EEECB3A8F0"
    assert second["take"] == "25"


async def test_compare_builds_the_recorded_shape() -> None:
    transport = FakeTransport(ok({"results": {"a": [], "b": [], "matchEntities": []}}))
    a = "A29A1AE5-57F9-4C42-95CD-143C90F4B55A"
    b = "41C4BB40-E667-416F-9541-63FD7E7FFFF5"
    await _client(transport).compare(a, b)
    path, params = transport.requests[0]
    assert path == "/v2/analysis/compare"
    assert dict(params) == {
        "a.signal.interests.entities": a,
        "b.signal.interests.entities": b,
        "filter.type": "urn:entity:brand",
        "take": "50",
    }


async def test_compare_rejects_non_entity_ids() -> None:
    transport = FakeTransport()
    with pytest.raises(QlooValidationError):
        await _client(transport).compare("not-a-uuid", "41C4BB40-E667-416F-9541-63FD7E7FFFF5")
    assert transport.requests == []


async def test_entity_validation_rejects_garbage_and_overlong_lists() -> None:
    transport = FakeTransport()
    client = _client(transport)
    with pytest.raises(QlooValidationError):
        await client.insights_places(["not-a-uuid"], location=(0.0, 0.0), radius_m=100)
    too_many = [f"00000000-0000-0000-0000-{index:012d}" for index in range(9)]
    with pytest.raises(QlooValidationError):
        await client.insights_heatmap(too_many, location=(0.0, 0.0), radius_m=100)
    assert transport.requests == []


async def test_response_rows_parse_and_the_call_record_cites_the_request() -> None:
    row = {
        "id": "urn:tag:genre:place:restaurant:bar",
        "name": "Bar",
        "type": "urn:tag:genre:place",
    }
    transport = FakeTransport(ok({"results": {"tags": [row]}}))
    response = await _client(transport).tags("bar", tag_types=["urn:tag:genre"], take=15)
    assert [tag.id for tag in response.rows] == ["urn:tag:genre:place:restaurant:bar"]
    call = response.call
    assert call is not None
    assert call.endpoint == "tags"
    assert call.path == "/v2/tags"
    assert call.parameters == "filter.query=bar&filter.tag.types=urn:tag:genre&take=15"
    assert call.status == 200
    assert call.attempts == 1
    assert call.rows == 1


async def test_warnings_parse_from_the_payload() -> None:
    payload = {
        "results": {"entities": []},
        "warnings": [
            {
                "type": "not_found",
                "signal.interests.entities": ["BC400638-8F5F-4F9C-9634-4833CA61E26F"],
            }
        ],
    }
    transport = FakeTransport(ok(payload))
    response = await _client(transport).insights_places(
        SEED, location=(18.93, 72.83), radius_m=8000
    )
    assert response.warnings[0].missing_entities == ["BC400638-8F5F-4F9C-9634-4833CA61E26F"]


async def test_missing_container_is_a_payload_error() -> None:
    transport = FakeTransport(ok({"results": {}}))
    with pytest.raises(QlooPayloadError) as excinfo:
        await _client(transport).tags("bar")
    assert "results.tags" in str(excinfo.value)
    assert excinfo.value.endpoint == "tags"


async def test_compare_payload_without_sides_is_a_payload_error() -> None:
    transport = FakeTransport(ok({"results": {"totally": "different"}}))
    with pytest.raises(QlooPayloadError):
        await _client(transport).compare(
            "A29A1AE5-57F9-4C42-95CD-143C90F4B55A", "41C4BB40-E667-416F-9541-63FD7E7FFFF5"
        )


async def test_fixture_mode_builds_the_fixture_transport(pack: FixturePack) -> None:
    client = QlooClient(make_settings(mode="fixture"))
    assert client.transport_name == "fixture"
    await client.aclose()


async def test_live_mode_builds_the_httpx_transport() -> None:
    client = QlooClient(make_settings(mode="live"))
    assert client.transport_name == "httpx"
    await client.aclose()
