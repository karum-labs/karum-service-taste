"""Door scouting (PLAN.md section 10): fixture replay and scripted transports.

The three recorded boards replay from the locked pack — including the collab
pair, where the ceramics category is legitimately empty. The demographics
batch for the top doors is the one call no preset contains, so those tests
script it explicitly through :class:`OverlayTransport` and assert the exact
request that went out.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack
from karum_service_taste.taste import scout_doors
from karum_service_taste.taste.schemas import EntityRefOut
from support import FakeTransport, OverlayTransport, make_settings, ok

#: Recorded seed orders; the 18 Oct calls ran with these exact signal lists
#: (the flagship five include Kinfolk, trimmed only at preset level).
FLAGSHIP_SEED = [
    EntityRefOut(id="E12201A5-CC50-40AF-97AE-C54A2CA303F7", type="urn:entity:brand", name="Muji"),
    EntityRefOut(
        id="0044C2D6-C96D-4571-8EFE-E81E8CF722D4", type="urn:entity:brand", name="Kinfolk"
    ),
    EntityRefOut(
        id="2B5888A0-8A41-4F23-9E1E-0F52DA29244A",
        type="urn:entity:place",
        name="Choplet Ceramic Studio & Gallery",
    ),
    EntityRefOut(
        id="6E449EFE-6006-4023-8EEC-0F1F720BDC94", type="urn:entity:place", name="BKLYN CLAY"
    ),
    EntityRefOut(
        id="98F7EBDF-987C-4741-B6F8-5C7511DC0021", type="urn:entity:place", name="Kettl Tea"
    ),
]
AUSTIN_SEED = [
    EntityRefOut(id="32F867B9-E6DF-44C3-BCE4-40160C7ED5E4", type="urn:entity:brand", name="Aesop"),
    EntityRefOut(
        id="41C4BB40-E667-416F-9541-63FD7E7FFFF5", type="urn:entity:brand", name="Ilegal Mezcal"
    ),
    EntityRefOut(
        id="BAF6317A-DF94-4C90-92AE-63F86560C21B", type="urn:entity:artist", name="Khruangbin"
    ),
]
COLABA_SEED = [
    EntityRefOut(
        id="0DE2E903-CCB5-4523-BAF0-3EC15514248C",
        type="urn:entity:place",
        name="Mary Lodge by Subko",
    ),
    EntityRefOut(
        id="BC400638-8F5F-4F9C-9634-4833CA61E26F",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Colaba",
    ),
    EntityRefOut(
        id="6CEDF620-266F-4B72-B14E-875532C321B1",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Bandra",
    ),
    EntityRefOut(
        id="617683A6-DCF8-4104-8A1A-7484D1F9601C",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Versova",
    ),
]

BROOKLYN = (40.7172, -73.9566)
AUSTIN = (30.2672, -97.7431)
COLABA = (18.93, 72.83)

CAFE = "urn:tag:genre:place:restaurant:cafe"
BAR = "urn:tag:genre:place:restaurant:bar"
GALLERY = "urn:tag:genre:place:art_gallery"
CERAMICS = "urn:tag:genre:place:ceramics"

ALPHA = "11111111-1111-4111-8111-111111111111"
BETA = "22222222-2222-4222-8222-222222222222"
GAMMA = "33333333-3333-4333-8333-333333333333"

EMPTY_DEMOGRAPHICS = {"results": {"demographics": []}}


def _client(transport: Any) -> QlooClient:
    return QlooClient(make_settings(), transport=transport)


def _door_row(
    entity_id: str,
    name: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    affinity: float = 0.9,
    tags: tuple[tuple[str, str, str], ...] = (),
    contributions: tuple[tuple[str, float], ...] = (),
) -> dict[str, Any]:
    """One live-shaped place row for scripted transports."""
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "name": name,
        "type": "urn:entity:place",
        "tags": [
            {"id": urn, "name": label, "type": kind, "weight": None} for urn, label, kind in tags
        ],
        "query": {"affinity": affinity},
    }
    if lat is not None:
        row["location"] = {"lat": lat, "lon": lon}
    if contributions:
        row["query"]["explainability"] = {
            "signal.interests.entities": [
                {"entity_id": entity, "score": score} for entity, score in contributions
            ]
        }
    return row


def _board(*rows: dict[str, Any]) -> dict[str, Any]:
    """A live-shaped place board payload (``results.entities``)."""
    return {"results": {"entities": list(rows)}}


def _profile_row(
    entity_id: str, ages: dict[str, float], *, male: float = 0.0, female: float = 0.0
) -> dict[str, Any]:
    """One live-shaped demographics row (nested under ``query``)."""
    return {
        "entity_id": entity_id,
        "query": {"age": ages, "gender": {"male": male, "female": female}},
    }


class _ProbeTransport:
    """A transport that tracks how many calls were in flight at once."""

    name = "probe"

    def __init__(self, *script: Any) -> None:
        self._script = list(script)
        self.max_in_flight = 0
        self._in_flight = 0

    async def get(self, path: str, params: list[tuple[str, str]]) -> Any:
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            await asyncio.sleep(0.01)
            return self._script.pop(0)
        finally:
            self._in_flight -= 1

    async def aclose(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Fixture replay: the three recorded boards and the collab pair
# ---------------------------------------------------------------------------


async def test_fixture_scouts_the_flagship_board(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        _client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=8000,
        category_tags=[CAFE],
    )

    assert result.error_code is ErrorCode.UNSPECIFIED
    assert [door.rank for door in result.doors] == list(range(1, 26))
    assert result.warnings == []

    top = result.doors[0]
    assert top.affinity_raw == pytest.approx(0.9307514984809063)
    assert top.distance_meters == pytest.approx(3155.65, abs=5)
    assert top.outside_city is False
    assert [(tag.urn, tag.label) for tag in top.shared_tags[:2]] == [
        ("urn:tag:nearby_attraction:qloo:udom_residence", "Udom residence"),
        ("urn:tag:genre:place:restaurant:brunch", "Brunch"),
    ]
    bklyn = next(
        contribution
        for contribution in top.explainability
        if contribution.entity_id == "6E449EFE-6006-4023-8EEC-0F1F720BDC94"
    )
    assert bklyn.score == pytest.approx(0.21254492619943002)
    assert bklyn.label == "BKLYN CLAY"

    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.demographics",
    ]
    assert result.evidence[0].parameters == (
        "feature.explainability=true"
        "&filter.location=POINT(-73.9566 40.7172)"
        "&filter.location.radius=8000"
        "&filter.tags=urn:tag:genre:place:restaurant:cafe"
        "&filter.type=urn:entity:place"
        "&signal.interests.entities="
        "E12201A5-CC50-40AF-97AE-C54A2CA303F7,"
        "0044C2D6-C96D-4571-8EFE-E81E8CF722D4,"
        "2B5888A0-8A41-4F23-9E1E-0F52DA29244A,"
        "6E449EFE-6006-4023-8EEC-0F1F720BDC94,"
        "98F7EBDF-987C-4741-B6F8-5C7511DC0021"
        "&take=25"
    )

    door_entry = next(
        entry
        for entry in pack.entries.values()
        if entry.path.parent.name == "brooklyn-flagship"
        and entry.path.stem == "insights-doors-cafe-tag"
    )
    top_ids = [row["entity_id"] for row in door_entry.rows][:8]
    assert result.evidence[1].parameters == (
        "filter.type=urn:demographics&signal.interests.entities=" + ",".join(top_ids)
    )
    assert len(transport.scripted) == 1
    assert transport.scripted[0][0] == "/v2/insights"
    assert ("signal.interests.entities", ",".join(top_ids)) in transport.scripted[0][1]

    for door in result.doors:
        assert door.evidence_ids == ["ev-0001"]  # the empty demographics batch matches no door
        assert door.demographics is None


async def test_fixture_surfaces_upstream_warnings(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        _client(transport),
        COLABA_SEED,
        location=COLABA,
        radius_meters=8000,
        category_tags=[CAFE],
    )

    assert result.warnings == ["not_found: BC400638-8F5F-4F9C-9634-4833CA61E26F"]
    assert len(result.doors) == 25
    assert result.error_code is ErrorCode.UNSPECIFIED


async def test_fixture_collab_sends_one_call_per_category(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        _client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=8000,
        category_tags=[GALLERY, CERAMICS],
    )

    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.place",
        "insights.demographics",
    ]
    assert "filter.tags=urn:tag:genre:place:art_gallery" in result.evidence[0].parameters
    assert "filter.tags=urn:tag:genre:place:ceramics" in result.evidence[1].parameters
    assert len(result.doors) == 25
    assert result.warnings == [f"category {CERAMICS} matched no doors"]
    assert all(door.evidence_ids == ["ev-0001"] for door in result.doors)


async def test_fixture_austin_board_uses_the_bar_tag(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=[BAR],
    )

    assert len(result.doors) == 25
    assert result.evidence[0].parameters == (
        "feature.explainability=true"
        "&filter.location=POINT(-97.7431 30.2672)"
        "&filter.location.radius=8000"
        "&filter.tags=urn:tag:genre:place:restaurant:bar"
        "&filter.type=urn:entity:place"
        "&signal.interests.entities=32F867B9-E6DF-44C3-BCE4-40160C7ED5E4,"
        "41C4BB40-E667-416F-9541-63FD7E7FFFF5,"
        "BAF6317A-DF94-4C90-92AE-63F86560C21B"
        "&take=25"
    )


# ---------------------------------------------------------------------------
# Scripted transports: fan-out, merging, misses, and the detail window
# ---------------------------------------------------------------------------


async def test_independent_calls_run_in_parallel_under_the_cap() -> None:
    transport = _ProbeTransport(
        ok(_board(_door_row(ALPHA, "Alpha"))),
        ok(_board(_door_row(BETA, "Beta"))),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a", "tag-b"],
        fanout_limit=2,
    )

    assert transport.max_in_flight == 2
    assert [door.entity.id for door in result.doors] == [ALPHA, BETA]


async def test_fanout_cap_of_one_serializes_the_calls() -> None:
    transport = _ProbeTransport(
        ok(_board(_door_row(ALPHA, "Alpha"))),
        ok(_board(_door_row(BETA, "Beta"))),
        ok(EMPTY_DEMOGRAPHICS),
    )
    await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a", "tag-b"],
        fanout_limit=1,
    )

    assert transport.max_in_flight == 1


async def test_merged_categories_dedupe_and_keep_encounter_order() -> None:
    transport = FakeTransport(
        ok(_board(_door_row(ALPHA, "Alpha"), _door_row(BETA, "Beta"))),
        ok(_board(_door_row(BETA, "Beta"), _door_row(GAMMA, "Gamma"))),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a", "tag-b"],
    )

    assert [door.entity.id for door in result.doors] == [ALPHA, BETA, GAMMA]
    assert [door.rank for door in result.doors] == [1, 2, 3]
    assert result.doors[1].evidence_ids == ["ev-0001"]
    assert result.doors[2].evidence_ids == ["ev-0002"]
    assert result.doors[0].distance_meters is None  # rows without a point stay unflagged
    assert result.doors[0].outside_city is False


async def test_empty_board_is_an_explicit_miss() -> None:
    transport = FakeTransport(ok(_board()))
    result = await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=[CERAMICS],
    )

    assert result.doors == []
    assert result.error_code is ErrorCode.EMPTY
    assert result.error_message == f"no doors matched {CERAMICS}"
    assert result.warnings == [f"category {CERAMICS} matched no doors"]
    assert len(result.evidence) == 1  # no demographics call when there are no doors
    assert len(transport.requests) == 1


async def test_empty_seed_is_validation() -> None:
    transport = FakeTransport()
    result = await scout_doors(_client(transport), [], location=AUSTIN, radius_meters=8000)

    assert result.error_code is ErrorCode.VALIDATION
    assert result.error_message == "seed is empty"
    assert transport.requests == []


async def test_nonpositive_radius_is_validation() -> None:
    transport = FakeTransport()
    result = await scout_doors(_client(transport), AUSTIN_SEED, location=AUSTIN, radius_meters=0)

    assert result.error_code is ErrorCode.VALIDATION
    assert "radius" in result.error_message
    assert transport.requests == []


async def test_top_door_demographics_map_onto_their_doors() -> None:
    transport = FakeTransport(
        ok(
            _board(
                _door_row(ALPHA, "Alpha"),
                _door_row(BETA, "Beta"),
                _door_row(GAMMA, "Gamma"),
            )
        ),
        ok(
            {
                "results": {
                    "demographics": [
                        _profile_row(
                            ALPHA, {"25_to_29": 0.2, "30_to_34": -0.05}, male=-0.1, female=0.1
                        ),
                        _profile_row(GAMMA, {"25_to_29": -0.3}),
                    ]
                }
            }
        ),
    )
    result = await scout_doors(
        _client(transport), AUSTIN_SEED, location=AUSTIN, radius_meters=8000, detail_limit=2
    )

    alpha, beta, gamma = result.doors
    assert alpha.demographics is not None
    assert [(bucket.label, bucket.delta) for bucket in alpha.demographics.age_buckets] == [
        ("25_to_29", 0.2),
        ("30_to_34", -0.05),
    ]
    assert alpha.demographics.male_delta == -0.1
    assert alpha.demographics.female_delta == 0.1
    assert alpha.evidence_ids == ["ev-0001", "ev-0002"]
    assert beta.demographics is None
    assert beta.evidence_ids == ["ev-0001"]
    assert gamma.demographics is None  # beyond the detail window
    assert gamma.evidence_ids == ["ev-0001"]
    assert transport.requests[1][1][1] == ("signal.interests.entities", f"{ALPHA},{BETA}")


async def test_interest_tags_ride_the_signal() -> None:
    transport = FakeTransport(ok(_board(_door_row(ALPHA, "Alpha"))), ok(EMPTY_DEMOGRAPHICS))
    await scout_doors(
        _client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        interest_tags=["urn:tag:genre:music:jazz"],
    )

    params = transport.requests[0][1]
    assert ("signal.interests.tags", "urn:tag:genre:music:jazz") in params


async def test_distance_and_outside_city_follow_the_point() -> None:
    transport = FakeTransport(
        ok(
            _board(
                _door_row(ALPHA, "Near", lat=30.2672, lon=-97.7400),
                _door_row(BETA, "Far", lat=32.7767, lon=-96.7970),
            )
        ),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(_client(transport), AUSTIN_SEED, location=AUSTIN, radius_meters=8000)

    near, far = result.doors
    assert near.distance_meters == pytest.approx(298, abs=5)
    assert near.outside_city is False
    assert far.distance_meters == pytest.approx(292_500, rel=0.05)
    assert far.outside_city is True
