"""Brand seed resolution (PLAN.md §8): fixture replay and scripted transports."""

from __future__ import annotations

from karum_service_taste.core.cache import TtlCache
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport
from karum_service_taste.qloo.models import SearchEntity
from karum_service_taste.taste import resolve_brand_seed
from karum_service_taste.taste.derived import LOW_CONFIDENCE
from support import FakeTransport, SleepingClock, make_settings, ok

MUJI_ID = "E12201A5-CC50-40AF-97AE-C54A2CA303F7"
SUBKO_ID = "0DE2E903-CCB5-4523-BAF0-3EC15514248C"
BROOKLYN_POINT = (40.7172, -73.9566)
COLABA_POINT = (18.93, 72.83)


def _client(transport: object) -> QlooClient:
    return QlooClient(make_settings(), transport=transport)  # type: ignore[arg-type]


def _fixture_client(pack: FixturePack) -> QlooClient:
    return QlooClient(make_settings(), transport=FixtureTransport(pack))


def _search_row(
    entity_id: str,
    name: str,
    *,
    place: bool = True,
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "entity_id": entity_id,
        "name": name,
        "types": ["urn:entity:place" if place else "urn:entity:brand"],
    }
    if lat is not None and lon is not None:
        row["location"] = {"lat": lat, "lon": lon}
    if city is not None:
        row["geocode"] = {"city": city}
    return row


# -- fixture replay against the locked pack ----------------------------------


async def test_fixture_resolves_a_brand_query(pack: FixturePack) -> None:
    resolution = await resolve_brand_seed(_fixture_client(pack), "MUJI")

    assert resolution.unresolved is False
    assert resolution.error_code is ErrorCode.UNSPECIFIED
    assert resolution.confidence == 1.0
    assert len(resolution.candidates) == 1
    candidate = resolution.candidates[0]
    assert candidate.entity.id == MUJI_ID
    assert candidate.entity.name == "Muji"
    assert candidate.entity.type == "urn:entity:brand"
    assert candidate.entity.city is None
    assert candidate.confidence == 1.0
    assert candidate.ambiguous is False
    assert candidate.in_city is False  # brand rows carry no point
    assert candidate.matched_query == "MUJI"
    assert resolution.queries[0].resolved is True
    assert resolution.queries[0].note == ""
    assert len(resolution.evidence) == 1
    call = resolution.evidence[0]
    assert call.endpoint == "search"
    assert call.parameters == "page=1&query=MUJI&take=5&types=urn:entity:brand"


async def test_fixture_vibe_query_resolves_as_a_place(pack: FixturePack) -> None:
    resolution = await resolve_brand_seed(
        _fixture_client(pack),
        "MUJI",
        fallback_queries=["Subko"],
        location=COLABA_POINT,
    )

    assert [outcome.text for outcome in resolution.queries] == ["MUJI", "Subko"]
    assert all(outcome.resolved for outcome in resolution.queries)
    assert len(resolution.candidates) == 6
    subko = next(c for c in resolution.candidates if c.matched_query == "Subko")
    assert subko.entity.id == SUBKO_ID
    assert subko.entity.name == "Mary Lodge by Subko"
    assert subko.entity.type == "urn:entity:place"
    assert subko.entity.city == "Mumbai"
    assert subko.confidence == 0.85
    assert subko.in_city is True
    assert subko.ambiguous is False
    assert resolution.confidence == 0.925
    assert len(resolution.evidence) == 2
    assert resolution.evidence[1].parameters == ("page=1&query=Subko&take=5&types=urn:entity:place")


async def test_fixture_weak_brand_rows_are_flagged(pack: FixturePack) -> None:
    resolution = await resolve_brand_seed(_fixture_client(pack), "Madre Mezcal")

    assert resolution.unresolved is False
    assert len(resolution.candidates) == 5
    assert all(candidate.ambiguous for candidate in resolution.candidates)
    assert resolution.candidates[0].confidence < LOW_CONFIDENCE
    assert "weak matches" in resolution.queries[0].note


async def test_fixture_colliding_names_are_ambiguous(pack: FixturePack) -> None:
    resolution = await resolve_brand_seed(
        _fixture_client(pack),
        "MUJI",
        fallback_queries=["Lilia"],
        location=BROOKLYN_POINT,
    )

    lilia = [c for c in resolution.candidates if c.matched_query == "Lilia"]
    assert len(lilia) == 5
    assert lilia[0].entity.name == "Lilia"
    assert lilia[0].in_city is True  # the New York row, ~350 m from the point
    assert lilia[1].in_city is False  # the Rio de Janeiro row
    assert lilia[0].ambiguous is True
    assert lilia[1].ambiguous is True


# -- scripted transports -----------------------------------------------------


async def test_scripted_transport_escalates_through_types() -> None:
    kinto = _search_row(
        "11111111-1111-1111-1111-111111111111",
        "Kinto",
        lat=30.26,
        lon=-97.74,
        city="Austin",
    )
    transport = FakeTransport(ok({"results": []}), ok({"results": [kinto]}))
    resolution = await resolve_brand_seed(_client(transport), "Kinto", location=(30.2672, -97.7431))

    assert resolution.queries[0].resolved is True
    assert "resolved as a place after an empty earlier lookup" in resolution.queries[0].note
    assert resolution.candidates[0].entity.id == "11111111-1111-1111-1111-111111111111"
    assert resolution.candidates[0].in_city is True
    assert len(resolution.evidence) == 2
    assert transport.requests[0][1] == [
        ("query", "Kinto"),
        ("types", "urn:entity:brand"),
        ("take", "5"),
        ("page", "1"),
    ]
    assert transport.requests[1][1] == [
        ("query", "Kinto"),
        ("types", "urn:entity:place"),
        ("take", "5"),
        ("page", "1"),
    ]


async def test_scripted_total_miss_is_unresolved() -> None:
    transport = FakeTransport(ok({"results": []}), ok({"results": []}), ok({"results": []}))
    resolution = await resolve_brand_seed(_client(transport), "Kinto")

    assert resolution.unresolved is True
    assert resolution.error_code is ErrorCode.UNRESOLVED
    assert resolution.confidence == 0.0
    assert resolution.candidates == []
    assert "Kinto" in resolution.error_message
    assert resolution.queries[0].resolved is False
    assert "no match" in resolution.queries[0].note
    assert len(resolution.evidence) == 3


async def test_scripted_partial_seed_lowers_confidence() -> None:
    muji = _search_row(MUJI_ID, "Muji", place=False)
    transport = FakeTransport(
        ok({"results": [muji]}),
        ok({"results": []}),
        ok({"results": []}),
        ok({"results": []}),
    )
    resolution = await resolve_brand_seed(_client(transport), "MUJI", fallback_queries=["zzz"])

    assert [outcome.resolved for outcome in resolution.queries] == [True, False]
    assert resolution.unresolved is False
    assert resolution.confidence == 0.5


async def test_city_hint_appears_when_no_row_is_in_city() -> None:
    chicago = _search_row(
        "22222222-2222-2222-2222-222222222222",
        "Subko",
        lat=41.786,
        lon=-88.08,
        city="Chicago",
    )
    transport = FakeTransport(ok({"results": [chicago]}))
    resolution = await resolve_brand_seed(
        _client(transport), "Subko", location=COLABA_POINT, city="Mumbai"
    )

    assert resolution.queries[0].note == "no row verified inside Mumbai"


async def test_blank_fallback_queries_are_ignored() -> None:
    muji = _search_row(MUJI_ID, "Muji", place=False)
    transport = FakeTransport(ok({"results": [muji]}))
    resolution = await resolve_brand_seed(_client(transport), "MUJI", fallback_queries=["", "   "])

    assert len(resolution.queries) == 1
    assert len(transport.requests) == 1


async def test_empty_brand_query_is_validation() -> None:
    transport = FakeTransport()
    resolution = await resolve_brand_seed(_client(transport), "   ")

    assert resolution.error_code is ErrorCode.VALIDATION
    assert resolution.unresolved is True
    assert resolution.error_message == "brand query is empty"
    assert transport.requests == []


# -- caching -----------------------------------------------------------------


async def test_cache_serves_repeat_lookups_without_calls() -> None:
    muji = _search_row(MUJI_ID, "Muji", place=False)
    transport = FakeTransport(ok({"results": [muji]}))
    virtual = SleepingClock()
    cache: TtlCache[list[SearchEntity]] = TtlCache(60, clock=virtual.clock)
    client = _client(transport)

    first = await resolve_brand_seed(client, "MUJI", cache=cache)
    second = await resolve_brand_seed(client, "MUJI", cache=cache)

    assert len(transport.requests) == 1
    assert first.candidates[0].entity.id == MUJI_ID
    assert second.candidates[0].entity.id == MUJI_ID
    assert second.evidence == []


async def test_cache_caches_negative_lookups() -> None:
    transport = FakeTransport(ok({"results": []}), ok({"results": []}), ok({"results": []}))
    virtual = SleepingClock()
    cache: TtlCache[list[SearchEntity]] = TtlCache(60, clock=virtual.clock)
    client = _client(transport)

    await resolve_brand_seed(client, "Kinto", cache=cache)
    second = await resolve_brand_seed(client, "Kinto", cache=cache)

    assert len(transport.requests) == 3
    assert second.unresolved is True
    assert second.evidence == []


async def test_cache_expiry_re_queries() -> None:
    transport = FakeTransport(*[ok({"results": []}) for _ in range(6)])
    virtual = SleepingClock()
    cache: TtlCache[list[SearchEntity]] = TtlCache(60, clock=virtual.clock)
    client = _client(transport)

    await resolve_brand_seed(client, "Kinto", cache=cache)
    virtual.now = 61.0
    await resolve_brand_seed(client, "Kinto", cache=cache)

    assert len(transport.requests) == 6
