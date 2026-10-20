"""The typed payload models eat every row the pack ships.

One parser path serves live calls and fixture replay — the models accept both
the live nesting and the redacted flattening — so this suite proves the
redacted side for every recording, plus raw-nested spot checks.
"""

from __future__ import annotations

import pytest

from karum_service_taste.qloo import models
from karum_service_taste.qloo.fixtures import FixtureEntry
from support import load_pack

PACK = load_pack()

MODEL_BY_KIND: dict[str, type[models.QlooModel]] = {
    "search": models.SearchEntity,
    "insights": models.PlaceRow,
    "heatmap": models.HeatmapCell,
    "locality": models.LocalityRow,
    "tags": models.CatalogTag,
    "demographics": models.DemographicsRow,
    "compare": models.CompareRow,
}

ENTRIES = sorted(PACK.entries.values(), key=lambda entry: entry.path.as_posix())
IDS = [entry.path.relative_to(PACK.root).as_posix() for entry in ENTRIES]


def _entry(relative_path: str) -> FixtureEntry:
    for entry in ENTRIES:
        if entry.path.relative_to(PACK.root).as_posix() == relative_path:
            return entry
    raise AssertionError(f"no recording at {relative_path}")  # pragma: no cover


@pytest.mark.parametrize("entry", ENTRIES, ids=IDS)
def test_every_recorded_row_parses(entry: FixtureEntry) -> None:
    model = MODEL_BY_KIND[entry.kind]
    parsed = [model.model_validate(row) for row in entry.rows]
    assert len(parsed) == len(entry.rows)


def test_search_row_facts() -> None:
    entry = _entry("qloo/austin-wholesale/search-aesop.json")
    row = models.SearchEntity.model_validate(entry.rows[0])
    assert row.entity_id == "32F867B9-E6DF-44C3-BCE4-40160C7ED5E4"
    assert row.name == "Aesop"
    assert row.types == ["urn:entity:brand"]
    assert row.location is None
    assert row.geocode is None


def test_search_row_lifts_geocode_from_live_properties() -> None:
    row = models.SearchEntity.model_validate(
        {
            "entity_id": "00000000-0000-0000-0000-000000000000",
            "name": "Franklin Barbecue",
            "types": ["urn:entity:place"],
            "properties": {"geocode": {"city": "Austin", "admin1_region": "Texas"}},
        }
    )
    assert row.geocode is not None
    assert row.geocode.city == "Austin"
    assert row.geocode.admin1_region == "Texas"


def test_place_row_facts() -> None:
    entry = _entry("qloo/austin-wholesale/insights-doors-category-bar.json")
    row = models.PlaceRow.model_validate(entry.rows[0])
    assert row.name == "Mezcalería Tobalá"
    assert row.subtype == "urn:entity:place"
    assert row.query.affinity is not None
    assert row.query.distance is not None and row.query.distance >= 0
    assert row.query.explainability is not None
    contributions = row.query.explainability["signal.interests.entities"]
    assert contributions
    assert all(contribution.entity_id and contribution.score >= 0 for contribution in contributions)
    assert row.tags and all(tag.id.startswith("urn:tag:") for tag in row.tags)
    assert row.properties.business_rating is not None
    assert row.properties.address is not None


def test_place_rows_carry_the_block_consumers_need() -> None:
    entry = _entry("qloo/austin-wholesale/insights-doors-baseline.json")
    rows = [models.PlaceRow.model_validate(row) for row in entry.rows]
    assert rows
    assert any(row.properties.good_for for row in rows)
    assert any(row.properties.hours for row in rows)
    assert any(row.properties.is_closed is not None for row in rows)


def test_place_properties_tolerate_a_non_list_good_for() -> None:
    properties = models.PlaceProperties.model_validate(
        {
            "address": "1 Main St",
            "good_for": "urn:tag:occasion:casual",
            "hours": None,
            "website": "https://example.com",
        }
    )
    assert properties.good_for == []
    assert properties.hours == {}
    assert properties.website == "https://example.com"


def test_place_row_keeps_price_facts() -> None:
    entry = _entry("qloo/austin-wholesale/insights-doors-baseline.json")
    rows = [models.PlaceRow.model_validate(row) for row in entry.rows]
    levels = [row.properties.price_level for row in rows if row.properties.price_level is not None]
    assert levels, "the baseline recording carries price levels"
    assert all(level is not None and level > 0 for level in levels)


def test_heatmap_cell_accepts_both_nestings() -> None:
    redacted = models.HeatmapCell.model_validate(
        {
            "geohash": "dr72j02",
            "location": {"lat": 40.78331, "lon": -73.959274},
            "affinity": 1,
            "affinity_rank": 0.9672270222222221,
            "popularity": 0.9985512495472655,
        }
    )
    live = models.HeatmapCell.model_validate(
        {
            "location": {"latitude": 40.78331, "longitude": -73.959274, "geohash": "dr72j02"},
            "query": {
                "affinity": 1,
                "affinity_rank": 0.9672270222222221,
                "popularity": 0.9985512495472655,
            },
        }
    )
    assert live == redacted
    assert live.location is not None
    assert live.location.lat == 40.78331


def test_locality_row_facts_and_live_nesting() -> None:
    entry = _entry("qloo/brooklyn-flagship/insights-heatmap-localities.json")
    row = models.LocalityRow.model_validate(entry.rows[0])
    assert row.name
    assert row.boundary is not None and row.boundary.startswith("MULTIPOLYGON")
    assert row.affinity is not None
    live = models.LocalityRow.model_validate(
        {"entity_id": row.entity_id, "name": row.name, "query": {"affinity": 0.5}}
    )
    assert live.affinity == 0.5


def test_demographics_row_facts_and_live_nesting() -> None:
    entry = _entry("qloo/brooklyn-flagship/demographics-seed.json")
    row = models.DemographicsRow.model_validate(entry.rows[0])
    assert row.age and row.gender
    assert set(row.gender) <= {"male", "female"}
    live = models.DemographicsRow.model_validate(
        {"entity_id": row.entity_id, "query": {"age": row.age, "gender": row.gender}}
    )
    assert live == row


def test_compare_row_facts_and_live_nesting() -> None:
    entry = _entry("qloo/austin-wholesale/compare-tobala-ilegal.json")
    row = models.CompareRow.model_validate(entry.rows[0])
    assert row.tag_id.startswith("urn:tag:")
    assert row.count == "1"
    live = models.CompareRow.model_validate(
        {
            "tag_id": row.tag_id,
            "name": row.name,
            "type": row.type,
            "subtype": row.subtype,
            "entity_id": row.entity_id,
            "query": {"count": 2},
        }
    )
    assert live.count == "2"


def test_warning_rows_name_the_not_found_signal() -> None:
    entry = _entry("qloo/mumbai-colaba-wholesale/insights-doors-untagged.json")
    assert entry.warnings
    warning = models.QlooWarning.model_validate(entry.warnings[0])
    assert warning.type == "not_found"
    assert warning.missing_entities == ["BC400638-8F5F-4F9C-9634-4833CA61E26F"]


def test_tags_row_facts() -> None:
    entry = _entry("qloo/tags/bar-genre.json")
    row = models.CatalogTag.model_validate(entry.rows[0])
    assert row.id.startswith("urn:tag:")
    assert row.name
    assert row.type is not None and row.type.startswith("urn:tag")
