"""The taste gRPC adapter maps a scout result onto the frozen proto."""

from karum.common.v1 import common_pb2
from karum.taste.v1 import taste_pb2
from karum_service_taste.grpcserv import scout_message
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.taste.schemas import (
    DoorOut,
    EntityRefOut,
    ScoutResult,
    SkipItemOut,
    SkipReason,
    SubScoreOut,
)


def test_scout_message_keeps_the_door_and_the_skip_reason():
    message = scout_message(
        ScoutResult(
            doors=[
                DoorOut(
                    entity=EntityRefOut(id="d-1", type="urn:entity:place", name="Whisler's", city="Austin"),
                    rank=1,
                    affinity=SubScoreOut(name="cultural_affinity", value=1.0, raw_value=0.91, inputs=["rank=1"]),
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
