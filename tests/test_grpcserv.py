"""The taste gRPC adapter maps a scout result onto the frozen proto."""

import asyncio

from karum.common.v1 import common_pb2
from karum.taste.v1 import taste_pb2
from karum_service_taste.grpcserv import TasteServicer, heatmap_message, scout_message
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.taste.schemas import (
    DoorOut,
    EntityRefOut,
    GeoPointOut,
    HeatmapCellOut,
    HeatmapResult,
    LocalityPolygonOut,
    PlaceFactsOut,
    ScoutResult,
    SkipItemOut,
    SkipReason,
    SubScoreOut,
)


def test_servicer_reuses_one_event_loop_across_rpcs():
    servicer = TasteServicer(object())  # type: ignore[arg-type]

    async def loop_id():
        return id(asyncio.get_running_loop())

    assert servicer._run(loop_id()) == servicer._run(loop_id())


def test_scout_message_keeps_the_door_and_the_skip_reason():
    message = scout_message(
        ScoutResult(
            doors=[
                DoorOut(
                    entity=EntityRefOut(
                        id="d-1", type="urn:entity:place", name="Whisler's", city="Austin"
                    ),
                    rank=1,
                    affinity=SubScoreOut(
                        name="cultural_affinity", value=1.0, raw_value=0.91, inputs=["rank=1"]
                    ),
                    evidence_ids=["ev-0001"],
                )
            ],
            skip_list=[
                SkipItemOut(
                    entity=EntityRefOut(id="d-9", type="urn:entity:place", name="Maggie Mae's"),
                    reason=SkipReason.LOW_AFFINITY,
                    reason_detail="below the floor",
                )
            ],
            error_code=ErrorCode.UNSPECIFIED,
        )
    )
    assert message.doors[0].entity.name == "Whisler's"
    assert message.doors[0].affinity.raw_value == 0.91
    assert message.skip_list[0].reason == taste_pb2.SKIP_REASON_CODE_LOW_AFFINITY
    assert message.error_code == common_pb2.ERROR_CODE_UNSPECIFIED


def test_heatmap_message_keeps_locality_geometry_and_place_facts():
    point = GeoPointOut(lat=40.71, lon=-73.96)
    message = heatmap_message(
        HeatmapResult(
            cells=[
                HeatmapCellOut(
                    location=point,
                    geohash="dr5ru",
                    affinity=0.8,
                    affinity_rank=3,
                    popularity=0.4,
                )
            ],
            localities=[
                LocalityPolygonOut(
                    name="Williamsburg",
                    affinity=0.8,
                    centroid=point,
                    polygon=[
                        GeoPointOut(lat=40.70, lon=-73.97),
                        GeoPointOut(lat=40.72, lon=-73.97),
                        GeoPointOut(lat=40.72, lon=-73.95),
                    ],
                )
            ],
            anchors=[
                EntityRefOut(
                    id="d-1",
                    type="urn:entity:place",
                    name="Whisler's",
                    place=PlaceFactsOut(
                        address="1100 E 5th St",
                        website="https://example.com",
                        phone="+1 512 555 0100",
                        hours="Mon 17:00-23:00",
                        lat=30.26,
                        lon=-97.73,
                    ),
                )
            ],
            error_code=ErrorCode.UNSPECIFIED,
        )
    )
    assert message.cells[0].geohash == "dr5ru"
    assert message.cells[0].affinity_rank == 3
    assert message.localities[0].polygon[2].longitude == -73.95
    assert message.anchors[0].place.address == "1100 E 5th St"
    assert message.anchors[0].place.location.latitude == 30.26
