"""Replay every recorded request end-to-end through the client.

For each of the pack's recordings, reconstruct the call the recording
describes, run it through a FixtureTransport-backed client, and assert the
typed response carries the recorded rows and provenance. This is the
"replay tests load the fixture pack, with no live network" gate of PLAN.md §7,
exercised across the whole pack rather than a sample.
"""

from __future__ import annotations

import re

import pytest

from karum_service_taste.qloo.canonical import parse_request
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.fixtures import FixtureEntry, FixtureTransport
from karum_service_taste.qloo.models import QlooResponse
from support import load_pack, make_settings

PACK = load_pack()
ENTRIES = sorted(PACK.entries.values(), key=lambda entry: entry.path.as_posix())
IDS = [entry.path.relative_to(PACK.root).as_posix() for entry in ENTRIES]

_POINT_RE = re.compile(r"^POINT\((?P<lon>[-\d.]+) (?P<lat>[-\d.]+)\)$")
_PAIR_RE = re.compile(r"^(?P<lat>[-\d.]+),(?P<lon>[-\d.]+)$")


def _values(entry: FixtureEntry) -> dict[str, str]:
    _, pairs = parse_request(entry.request)
    return dict(pairs)


def _ids(value: str) -> list[str]:
    return [part for part in value.split(",") if part]


async def _replay(client: QlooClient, entry: FixtureEntry) -> QlooResponse:
    values = _values(entry)
    path, _ = parse_request(entry.request)

    if path == "/search":
        location = None
        if values.get("filter.location"):
            match = _PAIR_RE.match(values["filter.location"])
            assert match, entry.request
            location = (float(match["lat"]), float(match["lon"]))
        return await client.search(
            values["query"],
            types=_ids(values["types"]) if values.get("types") else None,
            take=int(values["take"]),
            page=int(values["page"]) if values.get("page") else None,
            location=location,
            radius_miles=float(values["filter.radius"]) if values.get("filter.radius") else None,
            sort_by=values.get("sort_by"),
        )

    if path == "/v2/tags":
        return await client.tags(
            values["filter.query"],
            tag_types=_ids(values["filter.tag.types"]) if values.get("filter.tag.types") else None,
            take=int(values["take"]),
        )

    if path == "/v2/analysis/compare":
        return await client.compare(
            values["a.signal.interests.entities"],
            values["b.signal.interests.entities"],
            entity_type=values["filter.type"],
            take=int(values["take"]),
        )

    # Everything else is /v2/insights.
    filter_type = values["filter.type"]
    if filter_type == "urn:demographics":
        return await client.insights_demographics(
            _ids(values["signal.interests.entities"]),
            results_entities=_ids(values["filter.results.entities"])
            if values.get("filter.results.entities")
            else None,
            take=int(values["take"]) if values.get("take") else None,
        )

    match = _POINT_RE.match(values["filter.location"])
    assert match, entry.request
    location = (float(match["lat"]), float(match["lon"]))
    radius = float(values["filter.location.radius"])
    entities = _ids(values["signal.interests.entities"])

    if filter_type == "urn:heatmap":
        boundary = values.get("output.heatmap.boundary")
        if boundary == "urn:entity:locality":
            return await client.insights_localities(
                entities, location=location, radius_m=radius, take=int(values["take"])
            )
        return await client.insights_heatmap(
            entities,
            location=location,
            radius_m=radius,
            boundary=boundary,
            take=int(values["take"]),
        )

    assert filter_type == "urn:entity:place", entry.request
    return await client.insights_places(
        entities,
        location=location,
        radius_m=radius,
        category_tags=_ids(values["filter.tags"]) if values.get("filter.tags") else None,
        interest_tags=_ids(values["signal.interests.tags"])
        if values.get("signal.interests.tags")
        else None,
        results_entities=_ids(values["filter.results.entities"])
        if values.get("filter.results.entities")
        else None,
        take=int(values["take"]),
        explainability=values.get("feature.explainability") == "true",
    )


@pytest.mark.parametrize("entry", ENTRIES, ids=IDS)
async def test_recording_replays_through_the_client(entry: FixtureEntry) -> None:
    client = QlooClient(make_settings(), transport=FixtureTransport(PACK))
    response = await _replay(client, entry)

    rows = response.a if hasattr(response, "a") else response.rows
    assert len(rows) == len(entry.rows)

    call = response.call
    assert call is not None
    assert call.attempts == 1
    assert call.status == 200
    assert call.rows == len(entry.rows)
    assert len(response.warnings) == len(entry.warnings)
