"""Pack index, kind enforcement, reconstruction, and miss strictness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from karum_service_taste.qloo.errors import QlooFixtureError, QlooFixtureMissError
from karum_service_taste.qloo.fixtures import (
    FixturePack,
    FixtureTransport,
    expected_kinds,
    reconstruct_payload,
)


def test_pack_indexes_every_recording_without_duplicates(pack: FixturePack) -> None:
    files = list((pack.root / "qloo").rglob("*.json"))
    assert len(pack.entries) >= 70
    assert len(pack.entries) == len(files)
    assert pack.duplicates == {}


def test_lookup_matches_a_client_built_request(pack: FixturePack) -> None:
    entry = pack.lookup(
        "/search",
        [("query", "Aesop"), ("types", "urn:entity:brand"), ("take", "5"), ("page", "1")],
    )
    assert entry is not None
    assert entry.kind == "search"
    assert entry.rows[0]["name"] == "Aesop"


async def test_transport_serves_a_recording(pack: FixturePack) -> None:
    transport = FixtureTransport(pack)
    response = await transport.get(
        "/v2/tags",
        [("filter.query", "bar"), ("filter.tag.types", "urn:tag:genre"), ("take", "15")],
    )
    assert response.status == 200
    first = response.payload["results"]["tags"][0]
    assert first["id"].startswith("urn:tag:")


async def test_transport_miss_is_loud(pack: FixturePack) -> None:
    transport = FixtureTransport(pack)
    with pytest.raises(QlooFixtureMissError) as excinfo:
        await transport.get("/search", [("query", "no such recording")])
    message = str(excinfo.value)
    assert "no recording" in message
    assert "no such recording" in message


def test_expected_kinds_matrix() -> None:
    assert expected_kinds("/search", []) == frozenset({"search"})
    assert expected_kinds("/v2/tags", []) == frozenset({"tags"})
    assert expected_kinds("/v2/analysis/compare", []) == frozenset({"compare"})
    assert expected_kinds("/v2/insights", [("filter.type", "urn:entity:place")]) == frozenset(
        {"insights"}
    )
    assert expected_kinds("/v2/insights", [("filter.type", "urn:heatmap")]) == frozenset(
        {"heatmap"}
    )
    assert expected_kinds(
        "/v2/insights",
        [("filter.type", "urn:heatmap"), ("output.heatmap.boundary", "urn:entity:locality")],
    ) == frozenset({"locality"})
    assert expected_kinds("/v2/insights", [("filter.type", "urn:demographics")]) == frozenset(
        {"demographics"}
    )
    assert expected_kinds("/v2/insights", [("filter.type", "urn:tag")]) == frozenset()


def test_reconstruct_payload_shapes() -> None:
    rows: list[Any] = [{"id": "x"}]
    assert reconstruct_payload("search", rows, [])["results"] == rows
    assert reconstruct_payload("tags", rows, [])["results"] == {"tags": rows}
    assert reconstruct_payload("insights", rows, [])["results"] == {"entities": rows}
    assert reconstruct_payload("heatmap", rows, [])["results"] == {"heatmap": rows}
    assert reconstruct_payload("locality", rows, [])["results"] == {"entities": rows}
    assert reconstruct_payload("demographics", rows, [])["results"] == {"demographics": rows}
    compare = reconstruct_payload("compare", rows, [])["results"]
    assert compare == {"a": rows, "b": [], "matchEntities": [], "tags": []}
    with_warnings = reconstruct_payload("tags", rows, [{"type": "not_found"}])
    assert with_warnings["warnings"] == [{"type": "not_found"}]


def _write_pack(root: Path, documents: list[dict[str, Any]]) -> None:
    qloo = root / "qloo"
    qloo.mkdir(parents=True, exist_ok=True)
    for index, document in enumerate(documents):
        (qloo / f"file-{index}.json").write_text(json.dumps(document), encoding="utf-8")


def _envelope(request: str = "/search?query=x", **overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "fixture_version": 1,
        "kind": "search",
        "source": {
            "recording": "raw.json",
            "recorded": "2026-10-18 05:00:00",
            "label": "l",
            "status": 200,
            "request": request,
        },
        "rows": [{"entity_id": "A", "name": "X"}],
    }
    document.update(overrides)
    return document


def test_missing_pack_directory_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(QlooFixtureError) as excinfo:
        FixturePack(tmp_path / "nowhere")
    assert "TASTE_FIXTURES_DIR" in str(excinfo.value)


def test_duplicate_signatures_are_reported_first_wins(tmp_path: Path) -> None:
    _write_pack(
        tmp_path,
        [
            _envelope(request="/search?query=x&take=5"),
            _envelope(request="/search?take=5&query=x"),
        ],
    )
    pack = FixturePack(tmp_path)
    assert len(pack.entries) == 1
    assert len(pack.duplicates) == 1
    duplicate = next(iter(pack.duplicates.values()))
    assert [path.name for path in duplicate] == ["file-0.json", "file-1.json"]


def test_wrong_version_is_rejected(tmp_path: Path) -> None:
    _write_pack(tmp_path, [_envelope(fixture_version=2)])
    with pytest.raises(QlooFixtureError) as excinfo:
        FixturePack(tmp_path)
    assert "version" in str(excinfo.value)


def test_missing_rows_are_rejected(tmp_path: Path) -> None:
    document = _envelope()
    del document["rows"]
    _write_pack(tmp_path, [document])
    with pytest.raises(QlooFixtureError):
        FixturePack(tmp_path)


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    _write_pack(tmp_path, [_envelope(kind="mystery")])
    with pytest.raises(QlooFixtureError):
        FixturePack(tmp_path)


def test_missing_request_is_rejected(tmp_path: Path) -> None:
    document = _envelope()
    document["source"] = {
        key: value for key, value in document["source"].items() if key != "request"
    }
    _write_pack(tmp_path, [document])
    with pytest.raises(QlooFixtureError):
        FixturePack(tmp_path)
