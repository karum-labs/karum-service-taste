"""Tag resolution (PLAN.md §9): fixture replay for every campaign chip."""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport
from karum_service_taste.taste import resolve_tags
from support import FakeTransport, make_settings, ok

# Every chip the three campaigns send, with its verified URN, Qloo label, and
# the take its lock-pass probe recorded.
CAMPAIGN_CHIPS = [
    ("bar", "urn:tag:genre:place:restaurant:bar", "Bar", 15, 1.0),
    ("cafe", "urn:tag:genre:place:restaurant:cafe", "Cafe", 25, 1.0),
    ("ceramics", "urn:tag:genre:place:ceramics", "Ceramics", 25, 1.0),
    ("gallery", "urn:tag:genre:place:art_gallery", "Art gallery", 25, 0.85),
]


def _client(transport: object) -> QlooClient:
    return QlooClient(make_settings(), transport=transport)  # type: ignore[arg-type]


def _fixture_client(pack: FixturePack) -> QlooClient:
    return QlooClient(make_settings(), transport=FixtureTransport(pack))


# -- fixture replay against the locked pack ----------------------------------


@pytest.mark.parametrize(("chip", "urn", "label", "take", "confidence"), CAMPAIGN_CHIPS)
async def test_fixture_resolves_every_campaign_chip(
    pack: FixturePack,
    chip: str,
    urn: str,
    label: str,
    take: int,
    confidence: float,
) -> None:
    resolution = await resolve_tags(_fixture_client(pack), [chip])

    assert resolution.error_code is ErrorCode.UNSPECIFIED
    assert resolution.unresolved == []
    assert len(resolution.resolved) == 1
    accepted = resolution.resolved[0]
    assert accepted.urn == urn
    assert accepted.label == label
    assert accepted.type == "urn:tag:genre:place"
    assert accepted.confidence == confidence
    assert accepted.free_text is False
    assert len(resolution.evidence) == 1
    assert resolution.evidence[0].parameters == (
        f"filter.query={chip}&filter.tag.types=urn:tag:genre&take={take}"
    )


@pytest.mark.parametrize(
    ("chip", "urn"),
    [
        ("Bars and restaurants", "urn:tag:genre:place:restaurant:bar"),
        ("cafés", "urn:tag:genre:place:restaurant:cafe"),
        ("Pottery", "urn:tag:genre:place:ceramics"),
        ("Art galleries", "urn:tag:genre:place:art_gallery"),
    ],
)
async def test_fixture_aliases_map_to_the_catalog(pack: FixturePack, chip: str, urn: str) -> None:
    resolution = await resolve_tags(_fixture_client(pack), [chip])

    assert resolution.resolved[0].urn == urn
    assert resolution.resolved[0].free_text is False


async def test_fixture_urn_chip_passes_through_without_a_call(pack: FixturePack) -> None:
    resolution = await resolve_tags(_fixture_client(pack), ["urn:tag:genre:place:art_gallery"])

    assert resolution.resolved[0].urn == "urn:tag:genre:place:art_gallery"
    assert resolution.resolved[0].label == "Art gallery"
    assert resolution.resolved[0].type == "urn:tag:genre"
    assert resolution.resolved[0].confidence == 1.0
    assert resolution.resolved[0].free_text is False
    assert resolution.evidence == []


async def test_off_namespace_urn_chip_is_unresolved(pack: FixturePack) -> None:
    resolution = await resolve_tags(_fixture_client(pack), ["urn:tag:service_type:qloo:dine_in"])

    assert resolution.resolved == []
    assert resolution.unresolved[0].reason == "outside the allow-list"


# -- free text and allow-list behaviour (scripted) ----------------------------


async def test_free_text_needs_a_confident_hit() -> None:
    rows = [
        {
            "id": "urn:tag:genre:place:record_store",
            "name": "Record store",
            "type": "urn:tag:genre:place",
        },
        {
            "id": "urn:tag:genre:place:music_venue",
            "name": "Music venue",
            "type": "urn:tag:genre:place",
        },
    ]
    transport = FakeTransport(ok({"results": {"tags": rows}}))
    resolution = await resolve_tags(_client(transport), ["record store"])

    accepted = resolution.resolved[0]
    assert accepted.urn == "urn:tag:genre:place:record_store"
    assert accepted.free_text is True
    assert accepted.confidence == 1.0
    assert transport.requests[0][1] == [
        ("filter.query", "record store"),
        ("filter.tag.types", "urn:tag:genre"),
        ("take", "25"),
    ]


async def test_free_text_with_weak_rows_is_unresolved() -> None:
    rows = [
        {
            "id": "urn:tag:genre:place:restaurant:bar",
            "name": "Bar",
            "type": "urn:tag:genre:place",
        }
    ]
    transport = FakeTransport(ok({"results": {"tags": rows}}))
    resolution = await resolve_tags(_client(transport), ["shoes"])

    assert resolution.resolved == []
    assert resolution.unresolved[0].reason == "no confident hit"


async def test_allow_list_refuses_off_namespace_rows() -> None:
    rows = [
        {
            "id": "urn:tag:service_type:qloo:dine_in",
            "name": "Dine in",
            "type": "urn:tag:service_type",
        }
    ]
    transport = FakeTransport(ok({"results": {"tags": rows}}))
    resolution = await resolve_tags(_client(transport), ["dine in"])

    assert resolution.unresolved[0].reason == "outside the allow-list"


async def test_no_rows_is_a_confident_miss() -> None:
    transport = FakeTransport(ok({"results": {"tags": []}}))
    resolution = await resolve_tags(_client(transport), ["vinyl"])

    assert resolution.unresolved[0].reason == "no confident hit"


async def test_mixed_chips_keep_their_order() -> None:
    rows = [
        {
            "id": "urn:tag:genre:place:record_store",
            "name": "Record store",
            "type": "urn:tag:genre:place",
        }
    ]
    transport = FakeTransport(ok({"results": {"tags": rows}}), ok({"results": {"tags": []}}))
    resolution = await resolve_tags(_client(transport), ["record store", "vinyl mat"])

    assert [accepted.chip for accepted in resolution.resolved] == ["record store"]
    assert [miss.chip for miss in resolution.unresolved] == ["vinyl mat"]


async def test_blank_chips_stay_misses_without_calls() -> None:
    transport = FakeTransport()
    resolution = await resolve_tags(_client(transport), ["   "])

    assert resolution.unresolved[0].reason == "empty chip"
    assert transport.requests == []


async def test_no_chips_is_validation() -> None:
    transport = FakeTransport()
    resolution = await resolve_tags(_client(transport), [])

    assert resolution.error_code is ErrorCode.VALIDATION
    assert resolution.error_message == "no chips supplied"
    assert transport.requests == []
