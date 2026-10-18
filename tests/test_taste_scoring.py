"""Scoring (PLAN.md section 11): percentiles, D_demo, and the relative skip list.

Pure helpers are pinned directly. The recorded probes drive the fixture runs —
the ranked-50 pool call fixes each floor, the batch scores the candidates —
and the Colaba run covers the visible degradation when the pool probe cannot
be made (no recording exists for its four-entity seed).
"""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport
from karum_service_taste.taste import scout_doors
from karum_service_taste.taste.schemas import EntityRefOut, SkipReason
from karum_service_taste.taste.scoring import (
    demographic_subscore,
    percentile_of,
    resolve_skip_names,
    skip_item,
)
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
    GAMMA,
    FakeTransport,
    OverlayTransport,
    board,
    door_row,
    make_client,
    ok,
    profile_row,
)

#: The flagship skip pool, as the preset lists it (affinity-descending).
FLAGSHIP_SKIPS = [
    "55E6BA87-F930-4AF0-AD01-D2A3AF0CF782",  # Lilia
    "9B68AA9D-BDA3-479D-95AF-C057CA0F2BEA",  # Bakeri
    "1F7B4F4E-2443-4CEE-9B23-E3E54142A8AE",  # SEY Coffee
    "9A47479B-EBCC-4406-9174-220EBC59B691",  # Maison Premiere
    "46B3218C-4B68-4CA4-B871-9C2CB59DBEF6",  # Fresh Kills Bar
    "AF59EF83-C53B-45AB-A980-D5EEECB3A8F0",  # Devocion
    "94ED4726-A194-4DD1-8C8E-04741512A1E4",  # Cafe Mogador
    "1EB1DDC1-0907-46FC-8D07-DB1BBCD020CA",  # Butler
]

#: The names a naive Brooklyn walk would pitch, in the recorded spellings.
SKIP_NAMES = [
    "Lilia",
    "Bakeri",
    "Sey Coffee",
    "Maison Premiere",
    "Fresh Kills Bar",
    "Devocion",
    "Cafe Mogador",
    "Butler",
]

AUSTIN_CANDIDATES = [
    "AD3677DA-5D2D-4FBD-8DCA-93D7ED616938",  # Whisler's -- below the floor
    "314D0217-CAF0-4758-AB13-6C5CEB355431",  # Uchiko Austin -- below the floor
    "572A6EDD-A341-4C1D-8316-6DB97A55BE78",  # Maggie Mae's -- below the floor
    "AFB7D16C-D6E0-482D-9A12-41C17D9A9CCF",  # Blind Pig Pub -- below the floor
    "CE9EE2BD-D7AE-4349-B627-3D051D98AE77",  # Franklin Barbecue -- the control
]
AUSTIN_SKIPS = AUSTIN_CANDIDATES[:4]
FRANKLIN = AUSTIN_CANDIDATES[4]

COLABA_CANDIDATES = [
    "68A744F0-1CE7-4C73-9A60-80C7A5713F72",  # Leopold Cafe
    "AE5CB53B-F858-4FFC-8D87-2DDD803A9B2F",  # Cafe Mondegar
    "41966C27-754D-4135-931F-64CF4F2418CA",  # US CLUB
    "75C0A119-48D6-4E7A-B719-47269354E130",  # High Street Phoenix
    "F13D82F2-95EF-49CF-8EEF-7B838CA53668",  # Royal Halls NSCI
]

LILIA = FLAGSHIP_SKIPS[0]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_percentile_ranks_the_set() -> None:
    peers = [0.5, 0.7, 0.9]
    assert percentile_of(0.9, peers) == 1.0
    assert percentile_of(0.5, peers) == 0.0
    assert percentile_of(0.7, peers) == pytest.approx(0.5)
    assert percentile_of(0.42, [0.42]) == 1.0
    assert percentile_of(0.42, []) == 1.0
    # equal values share their percentile (strictly-below counting)
    assert percentile_of(0.5, [0.5, 0.5, 0.9]) == 0.0
    assert percentile_of(0.9, [0.5, 0.5, 0.9]) == 1.0


def test_demographic_subscore_maps_cosine_onto_zero_one() -> None:
    same = {"25_to_29": 0.2, "30_to_34": -0.1}
    aligned = demographic_subscore(same, same)
    assert aligned is not None
    assert aligned.name == "demographic_alignment"
    assert aligned.value == pytest.approx(1.0)
    assert aligned.raw_value == pytest.approx(1.0)
    assert aligned.inputs == ["age_buckets=2", "mapping=cosine01"]

    opposite = demographic_subscore({"25_to_29": 1.0}, {"25_to_29": -1.0})
    assert opposite is not None
    assert opposite.value == pytest.approx(0.0)

    orthogonal = demographic_subscore({"25_to_29": 1.0}, {"30_to_34": 1.0})
    assert orthogonal is not None
    assert orthogonal.value == pytest.approx(0.5)
    assert orthogonal.raw_value == pytest.approx(0.0)


def test_demographic_subscore_refuses_empty_inputs() -> None:
    assert demographic_subscore({}, {}) is None
    assert demographic_subscore({"a": 0.0}, {"a": 0.0}) is None
    assert demographic_subscore({"a": 1.0}, {}) is None


def test_skip_item_names_the_floor() -> None:
    entity = EntityRefOut(id=LILIA, type="urn:entity:place", name="Lilia")
    item = skip_item(entity, 0.9192, 0.9218, [0.93, 0.95])
    assert item.reason is SkipReason.LOW_AFFINITY
    assert item.reason_detail == "0.9192 below the returned floor 0.9218"
    assert item.affinity is not None
    assert item.affinity.name == "cultural_affinity"
    assert item.affinity.value == 0.0
    assert item.affinity.raw_value == 0.9192
    assert item.affinity.inputs == ["pool=2", "floor=0.9218"]


# ---------------------------------------------------------------------------
# Free-entry name resolution
# ---------------------------------------------------------------------------


async def test_fixture_resolves_the_skip_names(pack: FixturePack) -> None:
    resolution = await resolve_skip_names(
        make_client(FixtureTransport(pack)), SKIP_NAMES, location=BROOKLYN
    )

    assert resolution.ids == FLAGSHIP_SKIPS
    assert resolution.unresolved == []
    assert resolution.warnings == []
    assert len(resolution.evidence) == 8
    assert resolution.evidence[0].parameters == "page=1&query=Lilia&take=5&types=urn:entity:place"


async def test_unresolved_names_become_skip_items() -> None:
    transport = FakeTransport(ok({"results": []}))
    resolution = await resolve_skip_names(make_client(transport), ["Nowhere Cafe"])

    assert resolution.ids == []
    assert len(resolution.unresolved) == 1
    item = resolution.unresolved[0]
    assert item.reason is SkipReason.UNRESOLVED
    assert item.reason_detail == "never resolved in Qloo: no confident place row"
    assert item.entity.name == "Nowhere Cafe"
    assert item.affinity is None


async def test_name_pick_prefers_the_in_city_row() -> None:
    rows = [
        {
            "entity_id": "99999999-9999-4999-8999-999999999999",
            "name": "Lilia",
            "type": "urn:entity:place",
            "location": {"lat": -22.9068, "lon": -43.1729},
        },
        {
            "entity_id": LILIA,
            "name": "Lilia",
            "type": "urn:entity:place",
            "location": {"lat": 40.7175, "lon": -73.9524},
        },
    ]
    transport = FakeTransport(ok({"results": rows}))
    resolution = await resolve_skip_names(make_client(transport), ["Lilia"], location=BROOKLYN)

    assert resolution.ids == [LILIA]


# ---------------------------------------------------------------------------
# Fixture runs: the two relative floors and their degradations
# ---------------------------------------------------------------------------


async def test_fixture_flagship_skip_list_replays(pack: FixturePack) -> None:
    transport = OverlayTransport(pack, ok(EMPTY_DEMOGRAPHICS))
    result = await scout_doors(
        make_client(transport),
        FLAGSHIP_SEED,
        location=BROOKLYN,
        radius_meters=8000,
        category_tags=[CAFE],
        skip_candidate_ids=FLAGSHIP_SKIPS,
    )

    assert result.warnings == []
    assert [item.entity.id for item in result.skip_list] == FLAGSHIP_SKIPS
    assert all(item.reason is SkipReason.LOW_AFFINITY for item in result.skip_list)

    lilia = result.skip_list[0]
    assert lilia.entity.name == "Lilia"
    assert lilia.reason_detail == "0.9192 below the returned floor 0.9218"
    assert lilia.affinity is not None
    assert lilia.affinity.raw_value == pytest.approx(0.9191962244351138)
    assert lilia.affinity.value == 0.0  # below every row of the ranked pool
    assert lilia.affinity.inputs == ["pool=50", "floor=0.9218"]

    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.demographics",
        "insights.place",
        "insights.demographics",
        "insights.place",
    ]
    pool = result.evidence[2].parameters
    assert "take=50" in pool
    assert "feature.explainability" not in pool
    assert "filter.tags" not in pool
    batch = result.evidence[4].parameters
    assert "filter.results.entities=" + ",".join(FLAGSHIP_SKIPS) in batch
    assert "take=25" in batch
    assert len(transport.scripted) == 1  # only the door-demographics batch was scripted


async def test_fixture_austin_control_stays_off_the_skip_list(pack: FixturePack) -> None:
    door_entry = next(
        entry
        for entry in pack.entries.values()
        if entry.path.parent.name == "austin-wholesale"
        and entry.path.stem == "insights-doors-category-bar"
    )
    leader_id = door_entry.rows[0]["entity_id"]
    transport = OverlayTransport(
        pack,
        ok(
            {
                "results": {
                    "demographics": [
                        profile_row(
                            leader_id,
                            {"25_to_29": -0.3, "30_to_34": 0.1},
                            male=0.05,
                            female=0.1,
                        )
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
        category_tags=[BAR],
        skip_candidate_ids=AUSTIN_CANDIDATES,
    )

    assert result.warnings == []
    skip_ids = [item.entity.id for item in result.skip_list]
    assert skip_ids == AUSTIN_SKIPS
    assert FRANKLIN not in skip_ids  # inside the returned set -- the control stays on the board
    assert result.skip_list[0].reason_detail == "0.8343 below the returned floor 0.8386"

    leader = result.doors[0]
    assert leader.entity.id == leader_id
    assert leader.demographics is not None
    assert leader.demographic_alignment is not None
    assert leader.demographic_alignment.name == "demographic_alignment"
    assert 0.0 <= leader.demographic_alignment.value <= 1.0


async def test_fixture_colaba_degrades_to_the_board_floor(pack: FixturePack) -> None:
    transport = OverlayTransport(pack)
    result = await scout_doors(
        make_client(transport),
        COLABA_SEED,
        location=COLABA,
        radius_meters=8000,
        category_tags=[CAFE],
        skip_candidate_ids=COLABA_CANDIDATES,
    )

    assert result.warnings == [
        "not_found: BC400638-8F5F-4F9C-9634-4833CA61E26F",
        "ranked pool probe unavailable (QlooFixtureMissError); floor falls back to the door board",
        "door demographics unavailable (QlooFixtureMissError); alignment stays unverified",
    ]
    assert transport.scripted == []
    assert len(result.skip_list) == 5
    assert result.skip_list[0].entity.name == "Leopold Cafe"
    assert result.skip_list[0].reason_detail == "0.9171 below the returned floor 0.9295"
    assert result.skip_list[0].affinity.inputs == ["pool=25", "floor=0.9295"]
    assert [call.endpoint for call in result.evidence] == [
        "insights.place",
        "insights.demographics",
        "insights.place",
    ]


async def test_candidates_at_the_floor_are_kept_and_ties_break_by_id() -> None:
    transport = FakeTransport(
        ok(board(door_row(ALPHA, "Alpha", affinity=0.95))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(board(door_row(BETA, "Beta", affinity=0.9))),
        ok(EMPTY_DEMOGRAPHICS),
        ok(
            board(
                door_row(GAMMA, "Gamma", affinity=0.9),  # equal to the floor -- kept
                door_row(BETA, "Beta", affinity=0.85),
                door_row(ALPHA, "Alpha", affinity=0.85),
            )
        ),
    )
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=["tag-a"],
        skip_candidate_ids=[ALPHA, BETA, GAMMA],
    )

    assert [item.entity.id for item in result.skip_list] == [ALPHA, BETA]
    assert all(
        item.reason_detail == "0.8500 below the returned floor 0.9000" for item in result.skip_list
    )


async def test_empty_category_never_scores_skip_candidates() -> None:
    transport = FakeTransport(ok(board()))
    result = await scout_doors(
        make_client(transport),
        AUSTIN_SEED,
        location=AUSTIN,
        radius_meters=8000,
        category_tags=[CERAMICS],
        skip_candidate_ids=[ALPHA],
    )

    assert result.error_code is ErrorCode.EMPTY
    assert result.error_message == f"no doors matched {CERAMICS}"
    assert result.skip_list == []
    assert len(transport.requests) == 1
