"""Door scouting (PLAN.md sections 10-11): fixture replay and scripted transports.

The three recorded boards replay from the locked pack, and so does each
preset's seed-demographics call (the target cohort ``D_demo`` measures
against). The door-demographics batch is the one call no preset recorded;
tests either script it through :class:`OverlayTransport` or assert the
visible degradation the service reports when it cannot be made.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack
from karum_service_taste.taste import scout_doors
from support import (
    ALPHA,
    AUSTIN,
    AUSTIN_SEED,
    BAR,
    BETA,
    BROOKLYN,
    CAFE,
    CERAMICS,
    COLABA,
    COLABA_SEED,
    EMPTY_DEMOGRAPHICS,
    FLAGSHIP_SEED,
    GALLERY,
    GAMMA,
    FakeTransport,
    OverlayTransport,
    board,
    door_row,
    make_client,
    ok,
    profile_row,
)

SEED_IDS = ",".join(entry.id for entry in FLAGSHIP_SEED)


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
# Fixture replay: the three recorded boards
# ---------------------------------------------------------------------------


async def test_fixture_scouts_the_flagship_board(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        make_client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=8000,
        category_tags=[CAFE],
    )

    assert result.error_code is ErrorCode.UNSPECIFIED
    assert [door.rank for door in result.doors] == list(range(1, 26))
    assert result.warnings == []
    assert result.skip_list == []

    top = result.doors[0]
    assert top.affinity is not None
    assert top.affinity.name == "cultural_affinity"
    assert top.affinity.value == 1.0
    assert top.affinity.raw_value == pytest.approx(0.9307514984809063)
    assert top.affinity.inputs == ["rank=1", "shortlist=25"]
    assert result.doors[1].affinity.value == pytest.approx(23 / 24)
    assert result.doors[-1].affinity.value == 0.0
    assert top.demographic_alignment is None  # the scripted batch carried no profiles
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
    assert result.evidence[1].parameters == (
        "filter.type=urn:demographics&signal.interests.entities=" + SEED_IDS
    )

    door_entry = next(
        entry
        for entry in pack.entries.values()
        if entry.path.parent.name == "brooklyn-flagship"
        and entry.path.stem == "insights-doors-cafe-tag"
    )
    top_ids = [row["entity_id"] for row in door_entry.rows][:8]
    assert result.evidence[2].parameters == (
        "filter.type=urn:demographics&signal.interests.entities=" + ",".join(top_ids)
    )
    assert len(transport.scripted) == 1
    assert transport.scripted[0][0] == "/v2/insights"
    assert ("signal.interests.entities", ",".join(top_ids)) in transport.scripted[0][1]

    for door in result.doors:
        assert door.evidence_ids == ["ev-0001"]  # the empty batch matched no door
        assert door.demographics is None


async def test_fixture_surfaces_upstream_warnings(pack: FixturePack) -> None:
    transport = OverlayTransport(pack)
    result = await scout_doors(
        make_client(transport),
        COLABA_SEED,
        location=COLABA,
        radius_meters=8000,
        category_tags=[CAFE],
    )

    assert result.error_code is ErrorCode.UNSPECIFIED
    assert len(result.doors) == 25
    assert result.warnings == [
        "not_found: BC400638-8F5F-4F9C-9634-4833CA61E26F",
        "door demographics unavailable (QlooFixtureMissError); alignment stays unverified",
    ]
    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.demographics",
    ]


async def test_fixture_collab_sends_one_call_per_category(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        make_client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=8000,
        category_tags=[GALLERY, CERAMICS],
    )

    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.place",
        "insights.demographics",
        "insights.demographics",
    ]
    assert "filter.tags=urn:tag:genre:place:art_gallery" in result.evidence[0].parameters
    assert "filter.tags=urn:tag:genre:place:ceramics" in result.evidence[1].parameters
    assert len(result.doors) == 25
    assert result.warnings == [f"category {CERAMICS} matched no doors"]
    assert all(door.evidence_ids == ["ev-0001"] for door in result.doors)
    assert len(transport.scripted) == 1  # only the door-demographics batch was scripted


async def test_fixture_austin_board_uses_the_bar_tag(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=[BAR],
    )

    assert len(result.doors) == 25
    assert result.warnings == []
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
        ok(board(door_row(ALPHA, "Alpha", affinity=0.91))),
        ok(board(door_row(BETA, "Beta"))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a", "tag-b"],
        fanout_limit=2,
    )

    assert transport.max_in_flight == 2
    assert [door.entity.id for door in result.doors] == [ALPHA, BETA]
    assert [door.affinity.value for door in result.doors] == [1.0, 0.0]


async def test_fanout_cap_of_one_serializes_the_calls() -> None:
    transport = _ProbeTransport(
        ok(board(door_row(ALPHA, "Alpha"))),
        ok(board(door_row(BETA, "Beta"))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(EMPTY_DEMOGRAPHICS),
    )
    await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a", "tag-b"],
        fanout_limit=1,
    )

    assert transport.max_in_flight == 1


async def test_merged_categories_dedupe_and_keep_encounter_order() -> None:
    transport = FakeTransport(
        ok(board(door_row(ALPHA, "Alpha"), door_row(BETA, "Beta"))),
        ok(board(door_row(BETA, "Beta"), door_row(GAMMA, "Gamma"))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(
        make_client(transport),
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
    transport = FakeTransport(ok(board()))
    result = await scout_doors(
        make_client(transport),
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
    result = await scout_doors(make_client(transport), [], location=AUSTIN, radius_meters=8000)

    assert result.error_code is ErrorCode.VALIDATION
    assert result.error_message == "seed is empty"
    assert transport.requests == []


async def test_nonpositive_radius_is_validation() -> None:
    transport = FakeTransport()
    result = await scout_doors(
        make_client(transport), AUSTIN_SEED, location=AUSTIN, radius_meters=0
    )

    assert result.error_code is ErrorCode.VALIDATION
    assert "radius" in result.error_message
    assert transport.requests == []


async def test_top_door_demographics_map_onto_their_doors() -> None:
    transport = FakeTransport(
        ok(board(door_row(ALPHA, "Alpha"), door_row(BETA, "Beta"), door_row(GAMMA, "Gamma"))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(
            {
                "results": {
                    "demographics": [
                        profile_row(
                            ALPHA, {"25_to_29": 0.2, "30_to_34": -0.05}, male=-0.1, female=0.1
                        ),
                        profile_row(GAMMA, {"25_to_29": -0.3}),
                    ]
                }
            }
        ),
    )
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        detail_limit=2,
    )

    alpha, beta, gamma = result.doors
    assert alpha.demographics is not None
    assert [(bucket.label, bucket.delta) for bucket in alpha.demographics.age_buckets] == [
        ("25_to_29", 0.2),
        ("30_to_34", -0.05),
    ]
    assert alpha.demographics.male_delta == -0.1
    assert alpha.demographics.female_delta == 0.1
    assert alpha.evidence_ids == ["ev-0001", "ev-0003"]
    assert alpha.demographic_alignment is None  # no seed profile in this script
    assert beta.demographics is None
    assert beta.evidence_ids == ["ev-0001"]
    assert gamma.demographics is None  # beyond the detail window
    assert gamma.evidence_ids == ["ev-0001"]
    assert transport.requests[2][1][1] == ("signal.interests.entities", f"{ALPHA},{BETA}")


async def test_demographic_mismatch_rides_beside_d_demo() -> None:
    transport = FakeTransport(
        ok(board(door_row(ALPHA, "Alpha"))),
        ok({"results": {"demographics": [profile_row(AUSTIN_SEED[0].id, {"25_to_29": 1.0})]}}),
        ok({"results": {"demographics": [profile_row(ALPHA, {"25_to_29": -1.0})]}}),
    )
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
    )

    alpha = result.doors[0]
    assert alpha.demographic_alignment is not None
    assert alpha.demographic_alignment.value == 0.0
    assert result.warnings == [
        "demographic mismatch at Alpha: D_demo 0.00 runs against the brand cohort"
    ]


async def test_interest_tags_ride_the_signal() -> None:
    transport = FakeTransport(
        ok(board(door_row(ALPHA, "Alpha"))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(EMPTY_DEMOGRAPHICS),
    )
    await scout_doors(
        make_client(transport),
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
            board(
                door_row(ALPHA, "Near", lat=30.2672, lon=-97.7400),
                door_row(BETA, "Far", lat=32.7767, lon=-96.7970),
            )
        ),
        ok(EMPTY_DEMOGRAPHICS),
        ok(EMPTY_DEMOGRAPHICS),
    )
    result = await scout_doors(
        make_client(transport), AUSTIN_SEED, location=AUSTIN, radius_meters=8000
    )

    near, far = result.doors
    assert near.distance_meters == pytest.approx(298, abs=5)
    assert near.outside_city is False
    assert far.distance_meters == pytest.approx(292_500, rel=0.05)
    assert far.outside_city is True
