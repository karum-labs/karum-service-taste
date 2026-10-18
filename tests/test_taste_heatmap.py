"""Locality heatmap (PLAN.md section 12): fixture replay and corridor picking.

The flagship cells and locality polygons replay from the locked pack; the
fidelity test pins the recorded shapes (cell count, corridors, one polygon's
centroid). Scripted transports cover the corridor/anchors glue and every
degradation line the run reports when a layer cannot be drawn.
"""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack
from karum_service_taste.taste import AnchorPlace, locality_heatmap
from karum_service_taste.taste.schemas import EntityRefOut
from support import (
    ALPHA,
    BETA,
    BROOKLYN,
    FLAGSHIP_SEED,
    FakeTransport,
    OverlayTransport,
    make_client,
    ok,
)

SEED_PARAM = ",".join(entry.id for entry in FLAGSHIP_SEED)

SQUARE = "MULTIPOLYGON (((70 20, 71 20, 71 21, 70 21, 70 20)))"


def _cells(*rows: dict[str, object]) -> dict[str, object]:
    return {"results": {"heatmap": list(rows)}}


def _localities(*rows: dict[str, object]) -> dict[str, object]:
    return {"results": {"entities": list(rows)}}


def _cell() -> dict[str, object]:
    return {
        "geohash": "sq1",
        "location": {"lat": 20.5, "lon": 70.5},
        "affinity": 0.9,
        "affinity_rank": 0.5,
        "popularity": 0.125,
    }


async def test_fixture_replays_the_flagship_heatmap(pack: FixturePack) -> None:
    result = await locality_heatmap(
        make_client(OverlayTransport(pack)),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=10000,
        include_localities=True,
    )

    assert result.available is True
    assert result.error_code is ErrorCode.UNSPECIFIED
    assert result.warnings == []
    assert len(result.cells) == 5523

    first = result.cells[0]
    assert first.geohash == "dr72j02"
    assert first.location is not None
    assert (first.location.lat, first.location.lon) == pytest.approx((40.78331, -73.959274))
    assert first.affinity == 1.0
    assert first.affinity_rank == pytest.approx(0.9672270222222221)
    assert first.popularity == pytest.approx(0.9985512495472655)

    assert [call.endpoint for call in result.evidence] == ["insights.heatmap", "insights.locality"]
    assert result.evidence[0].parameters == (
        "filter.location=POINT(-73.9566 40.7172)"
        "&filter.location.radius=10000"
        "&filter.type=urn:heatmap"
        f"&signal.interests.entities={SEED_PARAM}"
        "&take=50"
    )
    assert result.evidence[1].parameters == (
        "filter.location=POINT(-73.9566 40.7172)"
        "&filter.location.radius=10000"
        "&filter.type=urn:heatmap"
        "&output.heatmap.boundary=urn:entity:locality"
        f"&signal.interests.entities={SEED_PARAM}"
        "&take=50"
    )

    assert result.corridors == ["New York", "Brooklyn", "Manhattan", "Tribeca", "Lower East Side"]
    assert result.anchors == []
    assert len(result.localities) == 83

    york = result.localities[0]
    assert york.name == "New York"
    assert york.affinity == 1.0
    assert york.disambiguation == "New York, New York, United States of America"
    assert york.centroid is not None
    assert (york.centroid.lat, york.centroid.lon) == pytest.approx(
        (40.663204, -73.938884), abs=1e-5
    )
    assert len(york.polygon) == 434
    assert (york.polygon[0].lat, york.polygon[0].lon) == pytest.approx(
        (40.498875, -74.258843), abs=1e-6
    )

    brooklyn = next(item for item in result.localities if item.name == "Brooklyn")
    assert brooklyn.affinity == pytest.approx(0.975609756097561)
    assert brooklyn.centroid is not None
    assert (brooklyn.centroid.lat, brooklyn.centroid.lon) == pytest.approx(
        (40.634178, -73.950188), abs=1e-5
    )
    assert len(brooklyn.polygon) == 240


async def test_cells_only_when_localities_are_not_requested(pack: FixturePack) -> None:
    result = await locality_heatmap(
        make_client(OverlayTransport(pack)),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=10000,
    )

    assert result.available is True
    assert len(result.cells) == 5523
    assert result.localities == []
    assert result.corridors == []
    assert result.anchors == []
    assert [call.endpoint for call in result.evidence] == ["insights.heatmap"]


async def test_heatmap_degrades_when_the_call_cannot_be_made(pack: FixturePack) -> None:
    result = await locality_heatmap(
        make_client(OverlayTransport(pack)),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=12345,
    )

    reason = "heatmap unavailable (QlooFixtureMissError); showing pins and the scout radius"
    assert result.available is False
    assert result.unavailable_reason == reason
    assert result.warnings == [reason]
    assert result.error_code is ErrorCode.VALIDATION
    assert result.error_message == reason
    assert result.cells == []
    assert result.evidence == []


async def test_empty_cells_hide_the_layer() -> None:
    transport = FakeTransport(ok({"results": {"heatmap": []}}))
    result = await locality_heatmap(
        make_client(transport), FLAGSHIP_SEED, location=BROOKLYN, radius_meters=10000
    )

    assert result.available is False
    assert result.unavailable_reason == "no heatmap cells matched the seed"
    assert result.error_code is ErrorCode.EMPTY
    assert result.error_message == "no heatmap cells matched the seed"
    assert len(result.evidence) == 1


async def test_locality_failure_keeps_the_density_layer(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(_cells(_cell())))
    result = await locality_heatmap(
        make_client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=12345,
        include_localities=True,
    )

    assert result.available is True
    assert len(result.cells) == 1
    assert result.localities == []
    assert result.corridors == []
    assert result.warnings == [
        "locality polygons unavailable (QlooFixtureMissError); corridors stay unnamed"
    ]


async def test_corridors_and_anchors_follow_the_polygons() -> None:
    transport = FakeTransport(
        ok(_cells(_cell())),
        ok(
            _localities(
                {
                    "entity_id": "55555555-5555-4555-8555-555555555555",
                    "name": "Corridor",
                    "disambiguation": "Unit Square",
                    "affinity": 0.9,
                    "boundary": SQUARE,
                },
                {
                    "entity_id": "66666666-6666-4666-8666-666666666666",
                    "name": "Broken",
                    "affinity": 0.8,
                    "boundary": "POLYGON ((oops))",
                },
            )
        ),
    )
    result = await locality_heatmap(
        make_client(transport),
        FLAGSHIP_SEED,
        location=(20.5, 70.5),
        radius_meters=10000,
        include_localities=True,
        anchor_places=[
            AnchorPlace(
                entity=EntityRefOut(id=ALPHA, type="urn:entity:place", name="Inside Corner"),
                lat=20.5,
                lon=70.5,
            ),
            AnchorPlace(
                entity=EntityRefOut(id=BETA, type="urn:entity:place", name="Outside Corner"),
                lat=19.0,
                lon=70.5,
            ),
        ],
    )

    assert result.available is True
    assert result.corridors == ["Corridor"]
    assert [anchor.name for anchor in result.anchors] == ["Inside Corner"]
    assert result.warnings == ["locality Broken carried an unreadable boundary"]
    assert len(result.localities) == 1
    corridor = result.localities[0]
    assert corridor.centroid is not None
    assert (corridor.centroid.lat, corridor.centroid.lon) == pytest.approx((20.5, 70.5))
    assert len(corridor.polygon) == 5


async def test_empty_seed_is_validation() -> None:
    transport = FakeTransport()
    result = await locality_heatmap(
        make_client(transport), [], location=BROOKLYN, radius_meters=10000
    )

    assert result.available is False
    assert result.error_code is ErrorCode.VALIDATION
    assert result.error_message == "seed is empty"
    assert transport.requests == []


async def test_nonpositive_radius_is_validation() -> None:
    transport = FakeTransport()
    result = await locality_heatmap(
        make_client(transport), FLAGSHIP_SEED, location=BROOKLYN, radius_meters=0
    )

    assert result.available is False
    assert result.error_code is ErrorCode.VALIDATION
    assert "radius" in result.error_message
    assert transport.requests == []
