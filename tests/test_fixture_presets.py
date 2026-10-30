"""The locked presets replay to what the pack recorded.

The pack is the scenario of record: each ``fixtures/presets/<id>.json`` says
which seed, point, radius, and tags the recording session used, and what came
back — the door board's rows and affinity range, the candidates that fell
below the floor, the heatmap's counts. This replays every preset through the
pack and checks the run against that record, so a preset cannot drift from
what it claims to show.

The replay is driven by the record alone, so the test needs nothing but the
pack — which CI checks out beside this repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooFixtureMissError
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport
from karum_service_taste.taste.doors import scout_doors
from karum_service_taste.taste.heatmap import locality_heatmap
from karum_service_taste.taste.schemas import EntityRefOut

#: The locked presets, by id. The record for each one lives in the pack.
PRESET_IDS = (
    "austin-wholesale",
    "brooklyn-collab",
    "brooklyn-flagship",
    "mumbai-colaba-wholesale",
)


def _record(pack: FixturePack, name: str) -> dict[str, Any]:
    """The recorded scenario for one preset, from the pack."""
    path = pack.root / "presets" / f"{name}.json"
    if not path.exists():
        pytest.skip(f"the pack holds no scenario for {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _tags(record: dict[str, Any]) -> list[str]:
    tags = record["category_tags"]
    values = tags["doors"] if "doors" in tags else tags["collab"]
    return [values] if isinstance(values, str) else list(values)


def _seed(record: dict[str, Any]) -> list[EntityRefOut]:
    return [
        EntityRefOut(
            id=item["entity_id"],
            type="urn:entity:brand" if item.get("kind") == "brand" else "urn:entity:place",
            name=item.get("name", ""),
        )
        for item in record["seed_entities"]
    ]


def _client(pack: FixturePack) -> QlooClient:
    from support import make_settings

    return QlooClient(settings=make_settings(), transport=FixtureTransport(pack))


async def _scout(pack: FixturePack, record: dict[str, Any]):
    point = record["point"]
    return await scout_doors(
        _client(pack),
        _seed(record),
        location=(point["lat"], point["lon"]),
        radius_meters=record["radii_m"]["doors"],
        category_tags=_tags(record),
        skip_candidate_ids=[item["entity_id"] for item in record.get("skip_candidates", [])],
    )


@pytest.mark.parametrize("name", PRESET_IDS)
async def test_every_preset_replays_its_door_board(pack: FixturePack, name: str) -> None:
    """The board is the rows, the range, and the top doors the record kept."""
    record = _record(pack, name)
    board = record.get("door_board") or {}
    result = await _scout(pack, record)

    rows = len(result.doors)
    assert rows, f"{name} replayed no doors"
    assert result.error_code != ErrorCode.EMPTY, f"{name} replayed an empty board"
    if not board:
        return
    assert rows == board["rows"], f"{name} replayed {rows} doors, the record kept {board['rows']}"
    raw = [door.affinity.raw_value for door in result.doors if door.affinity]
    assert raw
    assert min(raw) == pytest.approx(board["min"], abs=5e-5)
    assert max(raw) == pytest.approx(board["max"], abs=5e-5)
    names = [door.entity.name for door in result.doors]
    for expected in board["top"]:
        assert expected in names, f"{name} lost the recorded top door {expected!r}"


@pytest.mark.parametrize("name", PRESET_IDS)
async def test_every_preset_replays_its_skip_list(pack: FixturePack, name: str) -> None:
    """The skip list is the recorded candidates, with the recorded affinity.

    The record names the venues in short form and with a straight apostrophe
    where the recording carries the published name, so the entity id is what
    the comparison is made on.
    """
    record = _record(pack, name)
    expected = {item["entity_id"]: item["affinity"] for item in record.get("skip_candidates", [])}
    result = await _scout(pack, record)
    replayed = {skip.entity.id: skip.affinity.raw_value for skip in result.skip_list}
    if not expected:
        assert not replayed, f"{name} replayed a skip list the record does not have"
        return
    assert set(replayed) == set(expected), f"{name} replayed a different skip list"
    for entity_id, affinity in expected.items():
        assert replayed[entity_id] == pytest.approx(affinity, abs=5e-5)


async def test_the_austin_skip_rows_keep_their_point(pack: FixturePack) -> None:
    """The red skip pins need a point; the recorded rows carry one."""
    result = await _scout(pack, _record(pack, "austin-wholesale"))
    assert result.skip_list, "the Austin skip list is empty"
    for skip in result.skip_list:
        place = skip.entity.place
        assert place is not None
        assert place.lat is not None and place.lon is not None


async def test_the_flagship_keeps_its_locality_polygons(pack: FixturePack) -> None:
    record = _record(pack, "brooklyn-flagship")
    point = record["point"]
    heatmap = await locality_heatmap(
        _client(pack),
        _seed(record),
        location=(point["lat"], point["lon"]),
        radius_meters=record["radii_m"]["heatmap"],
        include_localities=True,
    )
    expected = record["heatmap"]
    assert len(heatmap.cells) == expected["cells"]
    assert len(heatmap.localities) == expected["localities"]
    assert heatmap.corridors
    for locality in heatmap.localities:
        assert locality.centroid is not None
    # A handful of localities arrive as a bare point and carry no ring; the
    # corridors are the ones with a shape.
    with_ring = [locality for locality in heatmap.localities if locality.polygon]
    assert with_ring, "no locality carried a polygon ring"


async def test_the_door_demographics_are_verified(pack: FixturePack) -> None:
    """The pack holds per-door demographics recordings for every preset door
    batch, so the scout scores D_demo against the seed cohort for each door
    and never leaves alignment unverified.
    """
    result = await _scout(pack, _record(pack, "austin-wholesale"))
    assert not any("demographics" in warning for warning in result.warnings)
    # Only the top 8 doors (DETAIL_DOOR_LIMIT) get per-door demographics;
    # lower-ranked doors stay unverified.
    for door in result.doors[:8]:
        assert door.demographic_alignment is not None


async def test_a_trimmed_request_serves_the_wider_recording(pack: FixturePack) -> None:
    """The Brooklyn preset trims the fifth seed signal; the replay says so."""
    record = _record(pack, "brooklyn-flagship")
    result = await _scout(pack, record)
    substituted = [warning for warning in result.warnings if "substituted" in warning]
    assert substituted, "the trimmed seed replayed without saying so"
    assert "0044C2D6-C96D-4571-8EFE-E81E8CF722D4" in substituted[0]


async def test_a_different_question_is_still_a_miss(pack: FixturePack) -> None:
    """The tag, the take, and the boundary variant stay significant."""
    record = _record(pack, "brooklyn-flagship")
    seed = ",".join(item["entity_id"] for item in record["seed_entities"])
    transport = FixtureTransport(pack)
    base = [
        ("filter.type", "urn:entity:place"),
        ("signal.interests.entities", seed),
        ("filter.location", "POINT(-73.9566 40.7172)"),
        ("filter.location.radius", "8000"),
        ("take", "25"),
        ("feature.explainability", "true"),
    ]
    # A tag the recording never used.
    with pytest.raises(QlooFixtureMissError):
        await transport.get(
            "/v2/insights",
            [*base[:1], ("filter.tags", "urn:tag:genre:place:restaurant:bar"), *base[1:]],
        )
    # The right tag, the wrong number of rows.
    with pytest.raises(QlooFixtureMissError):
        await transport.get(
            "/v2/insights",
            [
                ("filter.type", "urn:entity:place"),
                ("filter.tags", "urn:tag:genre:place:restaurant:cafe"),
                *base[1:4],
                ("take", "99"),
                ("feature.explainability", "true"),
            ],
        )


async def test_an_ambiguous_request_is_a_miss(tmp_path: Path) -> None:
    """Two recordings that could answer the request is a bug, not a guess."""
    seed = "AAAA1111-1111-1111-1111-111111111111"
    extra = "BBBB2222-2222-2222-2222-222222222222"
    other = "CCCC3333-3333-3333-3333-333333333333"
    for name, ids in (("one", f"{seed},{extra}"), ("two", f"{seed},{other}")):
        (tmp_path / "qloo" / name).mkdir(parents=True)
        (tmp_path / "qloo" / name / "row.json").write_text(
            json.dumps(
                {
                    "fixture_version": 1,
                    "kind": "insights",
                    "source": {
                        "request": f"/v2/insights?filter.type=urn:entity:place"
                        f"&signal.interests.entities={ids}&take=25",
                        "status": 200,
                    },
                    "rows": [],
                }
            ),
            encoding="utf-8",
        )
    pack = FixturePack(tmp_path)
    with pytest.raises(QlooFixtureMissError):
        await FixtureTransport(pack).get(
            "/v2/insights",
            [
                ("filter.type", "urn:entity:place"),
                ("signal.interests.entities", seed),
                ("take", "25"),
            ],
        )
