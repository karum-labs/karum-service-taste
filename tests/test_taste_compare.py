"""Audience compare (PLAN.md section 12): the recorded pairs and the degrade.

Both lock-pass pairs are cross-type (a door against a brand), so the recorded
overlap and ``matchEntities`` are empty and the result reports the degraded
chart (DI-22). Scripted transports pin the envelope mapping: overlap rows
from ``results.tags``, matching entities from ``results.matchEntities``.
"""

from __future__ import annotations

from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack
from karum_service_taste.taste import compare_audiences
from support import ALPHA, FakeTransport, OverlayTransport, make_client, ok

#: Mezcaleria Tobala (the door side) against Ilegal Mezcal (the brand side).
TOBALA = "A29A1AE5-57F9-4C42-95CD-143C90F4B55A"
ILEGAL = "41C4BB40-E667-416F-9541-63FD7E7FFFF5"

#: Leopold Cafe (the door side) against the 16 Oct probe counterpart brand.
LEOPOLD = "68A744F0-1CE7-4C73-9A60-80C7A5713F72"
PROBE_BRAND = "B6DA90E2-E073-4CE1-83CC-678F089C92EC"

REASON = "the pair shares no tags and no matching entities; the conquest chart stays hidden"


async def test_austin_pair_replays_with_the_chart_degraded(pack: FixturePack) -> None:
    result = await compare_audiences(make_client(OverlayTransport(pack)), TOBALA, ILEGAL)

    assert result.available is False
    assert result.match_entities_present is False
    assert result.overlap_tags == []
    assert result.match_entities == []
    assert result.unavailable_reason == REASON
    assert result.warnings == [REASON]
    assert result.error_code is ErrorCode.UNSPECIFIED
    assert result.error_message == REASON
    assert len(result.evidence) == 1

    call = result.evidence[0]
    assert call.endpoint == "compare"
    assert call.path == "/v2/analysis/compare"
    assert call.parameters == (
        f"a.signal.interests.entities={TOBALA}"
        f"&b.signal.interests.entities={ILEGAL}"
        "&filter.type=urn:entity:brand"
        "&take=50"
    )
    assert call.rows == 12


async def test_colaba_probe_replays(pack: FixturePack) -> None:
    result = await compare_audiences(make_client(OverlayTransport(pack)), LEOPOLD, PROBE_BRAND)

    assert result.available is False
    assert result.evidence[0].rows == 44


async def test_overlap_renders_when_tags_are_shared() -> None:
    transport = FakeTransport(
        ok(
            {
                "results": {
                    "tags": [
                        {
                            "tag_id": "urn:tag:offerings:place:alcohol",
                            "name": "Alcohol",
                            "type": "urn:tag",
                            "subtype": "urn:tag:offerings:place",
                            "entity_id": "01FE8354-6E33-48DF-B188-50E056F3995E",
                            "count": "3",
                        },
                        {
                            "tag_id": "urn:tag:offerings:place:coffee",
                            "name": "Coffee",
                            "type": "urn:tag",
                            "subtype": "urn:tag:offerings:place",
                            "entity_id": "2B5888A0-8A41-4F23-9E1E-0F52DA29244A",
                            "count": "1",
                        },
                    ],
                    "a": [],
                    "b": [],
                    "matchEntities": [],
                }
            }
        )
    )
    result = await compare_audiences(make_client(transport), LEOPOLD, PROBE_BRAND)

    assert result.available is True
    assert result.match_entities_present is False
    assert result.error_code is ErrorCode.UNSPECIFIED
    assert [(tag.urn, tag.label, tag.type) for tag in result.overlap_tags] == [
        ("urn:tag:offerings:place:alcohol", "Alcohol", "urn:tag:offerings:place"),
        ("urn:tag:offerings:place:coffee", "Coffee", "urn:tag:offerings:place"),
    ]
    assert result.warnings == []


async def test_matching_entities_mark_the_pair_present() -> None:
    transport = FakeTransport(
        ok(
            {
                "results": {
                    "tags": [],
                    "a": [],
                    "b": [],
                    "matchEntities": [
                        {
                            "tag_id": "urn:tag:test",
                            "name": "Corner Store",
                            "type": "urn:entity:place",
                            "entity_id": ALPHA,
                            "count": None,
                        }
                    ],
                }
            }
        )
    )
    result = await compare_audiences(make_client(transport), LEOPOLD, PROBE_BRAND)

    assert result.available is True
    assert result.match_entities_present is True
    assert [(item.id, item.type, item.name) for item in result.match_entities] == [
        (ALPHA, "urn:entity:place", "Corner Store")
    ]


async def test_compare_degrades_when_the_call_cannot_be_made(pack: FixturePack) -> None:
    result = await compare_audiences(make_client(OverlayTransport(pack)), ALPHA, PROBE_BRAND)

    reason = "compare unavailable (QlooFixtureMissError); the conquest chart stays hidden"
    assert result.available is False
    assert result.unavailable_reason == reason
    assert result.warnings == [reason]
    assert result.error_code is ErrorCode.VALIDATION
    assert result.evidence == []
