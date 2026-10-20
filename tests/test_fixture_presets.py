"""The locked presets replay through the pack, and the substitution is visible.

The four judge presets were curated below what the recordings captured: the
Brooklyn session ran with a fifth seed signal, the Mumbai one with a fourth,
and the Austin skip probe scored five candidates where the preset lists the
four that fell below the floor. The pack therefore has no recording for the
preset's own request, and the replay serves the recording that answers the
same question with more entities — saying so in the run's warnings.

These tests pin that behaviour: the presets replay, the skip rows keep their
points, the flagships keep their locality polygons, and a request that is not
merely trimmed is still a miss.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooFixtureMissError
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport
from karum_service_taste.taste.doors import scout_doors
from karum_service_taste.taste.heatmap import locality_heatmap
from karum_service_taste.taste.schemas import EntityRefOut

#: The gateway's locked catalogue, which is what the demo sends.
GATEWAY_PRESETS = (
    Path(__file__).resolve().parents[2] / "karum-server" / "internal" / "presets" / "presets.go"
)

_UUID = r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"


def _presets() -> dict[str, dict]:
    """The preset catalogue the gateway ships, parsed for these tests."""
    source = GATEWAY_PRESETS.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    for block in re.split(r"(?m)^\t\t\{\n", source):
        ident = re.search(r'ID:\s*"([a-z0-9-]+)"', block)
        if ident is None:
            continue
        seed = re.search(r"Seed: \[\]Entity\{(.*?)\n\t\t\t\}", block, re.S)
        skip = re.search(r"SkipCandidateIDs: \[\]string\{(.*?)\}", block, re.S)
        tags = re.search(r"CategoryTags: \[\]string\{(.*?)\}", block, re.S)
        point = re.search(r"Lat:\s*([-\d.]+),\s*Lng:\s*([-\d.]+)", block)
        radius = re.search(r"RadiusMeters:\s*(\d+)", block)
        heat = re.search(r"HeatmapRadius:\s*(\d+)", block)
        out[ident.group(1)] = {
            "seed": [
                {"id": i, "name": n, "type": t}
                for i, n, t in re.findall(
                    rf'ID:\s*"({_UUID})",\s*Name:\s*"([^"]*)",\s*Type:\s*"([^"]*)"',
                    seed.group(1) if seed else "",
                )
            ],
            "skip": re.findall(rf'"({_UUID})"', skip.group(1)) if skip else [],
            "tags": re.findall(r'"([^"]+)"', tags.group(1)) if tags else [],
            "lat": float(point.group(1)) if point else 0.0,
            "lng": float(point.group(2)) if point else 0.0,
            "radius": int(radius.group(1)) if radius else 8000,
            "heatmap_radius": int(heat.group(1)) if heat else 0,
        }
    return out


PRESETS = _presets()


def _client(pack: FixturePack) -> QlooClient:
    return QlooClient(settings=make_settings(), transport=FixtureTransport(pack))


def make_settings():  # noqa: ANN201 - the shared test settings
    from support import make_settings as build

    return build()


def _seed(preset: dict) -> list[EntityRefOut]:
    return [
        EntityRefOut(id=item["id"], type=item["type"], name=item["name"]) for item in preset["seed"]
    ]


@pytest.mark.parametrize("name", sorted(PRESETS))
async def test_every_preset_replays_its_boards(pack: FixturePack, name: str) -> None:
    preset = PRESETS[name]
    result = await scout_doors(
        _client(pack),
        _seed(preset),
        location=(preset["lat"], preset["lng"]),
        radius_meters=preset["radius"],
        category_tags=preset["tags"],
        skip_candidate_ids=preset["skip"],
    )
    door_count = len(result.doors)
    empty = result.error_code == ErrorCode.EMPTY
    assert door_count, f"{name} replayed no doors"
    assert not empty, f"{name} replayed an empty board"


async def test_the_austin_skip_rows_keep_their_point(pack: FixturePack) -> None:
    """The red skip pins need a point; the recorded rows carry one."""
    preset = PRESETS["austin-wholesale"]
    result = await scout_doors(
        _client(pack),
        _seed(preset),
        location=(preset["lat"], preset["lng"]),
        radius_meters=preset["radius"],
        category_tags=preset["tags"],
        skip_candidate_ids=preset["skip"],
    )
    assert result.skip_list, "the Austin skip list is empty"
    for skip in result.skip_list:
        place = skip.entity.place
        assert place is not None
        assert place.lat is not None and place.lon is not None


async def test_the_flagship_keeps_its_locality_polygons(pack: FixturePack) -> None:
    preset = PRESETS["brooklyn-flagship"]
    heatmap = await locality_heatmap(
        _client(pack),
        _seed(preset),
        location=(preset["lat"], preset["lng"]),
        radius_meters=preset["heatmap_radius"],
        include_localities=True,
    )
    assert heatmap.cells
    assert heatmap.localities, "the flagship replayed no locality polygons"
    assert heatmap.corridors
    for locality in heatmap.localities:
        assert locality.centroid is not None
    # A handful of localities arrive as a bare point and carry no ring; the
    # corridors are the ones with a shape.
    with_ring = [locality for locality in heatmap.localities if locality.polygon]
    assert with_ring, "no locality carried a polygon ring"


async def test_the_substitution_is_visible_in_the_run(pack: FixturePack) -> None:
    """A replayed call says so; the operator sees it in the warnings."""
    preset = PRESETS["brooklyn-flagship"]
    result = await scout_doors(
        _client(pack),
        _seed(preset),
        location=(preset["lat"], preset["lng"]),
        radius_meters=preset["radius"],
        category_tags=preset["tags"],
        skip_candidate_ids=preset["skip"],
    )
    substituted = [w for w in result.warnings if "substituted" in w]
    assert substituted, "the trimmed seed replayed without saying so"
    assert "Kinfolk" not in substituted[0]  # the ids, not the names
    assert "0044C2D6-C96D-4571-8EFE-E81E8CF722D4" in substituted[0]


async def test_a_trimmed_request_serves_the_wider_recording(pack: FixturePack) -> None:
    preset = PRESETS["brooklyn-flagship"]
    match = pack.match(
        "/v2/insights",
        [
            ("filter.type", "urn:entity:place"),
            ("filter.tags", "urn:tag:genre:place:restaurant:cafe"),
            ("signal.interests.entities", ",".join(i["id"] for i in preset["seed"])),
            ("filter.location", "POINT(-73.9566 40.7172)"),
            ("filter.location.radius", "8000"),
            ("take", "25"),
            ("feature.explainability", "true"),
        ],
    )
    assert match is not None
    assert match.substituted
    assert match.omitted == ("0044C2D6-C96D-4571-8EFE-E81E8CF722D4",)
    assert match.entry.path.stem == "insights-doors-cafe-tag"


async def test_a_different_question_is_still_a_miss(pack: FixturePack) -> None:
    """The tag, the take, and the boundary variant stay significant."""
    preset = PRESETS["brooklyn-flagship"]
    seed = ",".join(i["id"] for i in preset["seed"])
    with pytest.raises(QlooFixtureMissError):
        await FixtureTransport(pack).get(
            "/v2/insights",
            [
                ("filter.type", "urn:entity:place"),
                ("filter.tags", "urn:tag:genre:place:restaurant:bar"),
                ("signal.interests.entities", seed),
                ("filter.location", "POINT(-73.9566 40.7172)"),
                ("filter.location.radius", "8000"),
                ("take", "25"),
                ("feature.explainability", "true"),
            ],
        )
    with pytest.raises(QlooFixtureMissError):
        await FixtureTransport(pack).get(
            "/v2/insights",
            [
                ("filter.type", "urn:entity:place"),
                ("filter.tags", "urn:tag:genre:place:restaurant:cafe"),
                ("signal.interests.entities", seed),
                ("filter.location", "POINT(-73.9566 40.7172)"),
                ("filter.location.radius", "8000"),
                ("take", "99"),
                ("feature.explainability", "true"),
            ],
        )


async def test_an_ambiguous_request_is_a_miss(tmp_path: Path) -> None:
    """Two recordings that could answer the request is a bug, not a guess."""
    import json

    def envelope(request: str, name: str) -> None:
        (tmp_path / "qloo" / name).mkdir(parents=True)
        (tmp_path / "qloo" / name / "row.json").write_text(
            json.dumps(
                {
                    "fixture_version": 1,
                    "kind": "insights",
                    "source": {"request": request, "status": 200},
                    "rows": [],
                }
            ),
            encoding="utf-8",
        )

    seed = "AAAA1111-1111-1111-1111-111111111111"
    extra = "BBBB2222-2222-2222-2222-222222222222"
    envelope(
        f"/v2/insights?filter.type=urn:entity:place&signal.interests.entities={seed},{extra}"
        "&take=25",
        "one",
    )
    envelope(
        f"/v2/insights?filter.type=urn:entity:place&signal.interests.entities={seed},"
        "CCCC3333-3333-3333-3333-333333333333&take=25",
        "two",
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
