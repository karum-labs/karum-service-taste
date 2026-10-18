"""Test helpers shared across the Qloo suites.

``conftest.py`` exposes the pytest fixtures; this module holds the plain
classes and functions so test modules can import them directly — including at
module import time, where pytest fixtures cannot help.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from karum_service_taste.core.config import Settings
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import QlooFixtureMissError
from karum_service_taste.qloo.fixtures import (
    REPO_ROOT,
    FixturePack,
    FixtureTransport,
    resolve_fixtures_dir,
)
from karum_service_taste.qloo.transport import TransportResponse
from karum_service_taste.taste.schemas import EntityRefOut

#: CI sets this so a missing pack is a failure, not a skip.
REQUIRED = os.environ.get("TASTE_REQUIRE_FIXTURES") == "1"

MISSING_PACK_MESSAGE = (
    "fixture pack not found at {directory}; check out karum-infra next to this "
    "repo or set TASTE_FIXTURES_DIR"
)


def resolve_pack_dir() -> Path:
    """TASTE_FIXTURES_DIR when set, else the sibling karum-infra checkout."""
    env = os.environ.get("TASTE_FIXTURES_DIR")
    if env:
        candidate = Path(env)
        return candidate if candidate.is_absolute() else (REPO_ROOT / candidate).resolve()
    return resolve_fixtures_dir(Path("../karum-infra/fixtures"))


def load_pack() -> FixturePack:
    """The pack, or a module-level skip when it is not checked out."""
    directory = resolve_pack_dir()
    if not (directory / "qloo").is_dir():
        message = MISSING_PACK_MESSAGE.format(directory=directory)
        if REQUIRED:
            raise RuntimeError(message)
        pytest.skip(message, allow_module_level=True)
    return FixturePack(directory)


class FakeTransport:
    """Scripted transport: records requests and plays queued answers."""

    name = "fake"

    def __init__(self, *script: TransportResponse | Exception) -> None:
        self.script = list(script)
        self.requests: list[tuple[str, list[tuple[str, str]]]] = []
        self.closed = False

    async def get(self, path: str, params: list[tuple[str, str]]) -> TransportResponse:
        self.requests.append((path, list(params)))
        if not self.script:
            raise AssertionError("FakeTransport ran out of scripted responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self) -> None:
        self.closed = True


def ok(
    payload: Any, *, headers: dict[str, str] | None = None, status: int = 200
) -> TransportResponse:
    """A scripted answer for :class:`FakeTransport`."""
    return TransportResponse(status=status, headers=dict(headers or {}), payload=payload)


# --- Taste-layer fixtures -------------------------------------------------
#
# Recorded seed orders: the 18 Oct calls ran with these exact signal lists
# (the flagship five include Kinfolk, trimmed only at preset level).

FLAGSHIP_SEED = [
    EntityRefOut(id="E12201A5-CC50-40AF-97AE-C54A2CA303F7", type="urn:entity:brand", name="Muji"),
    EntityRefOut(
        id="0044C2D6-C96D-4571-8EFE-E81E8CF722D4", type="urn:entity:brand", name="Kinfolk"
    ),
    EntityRefOut(
        id="2B5888A0-8A41-4F23-9E1E-0F52DA29244A",
        type="urn:entity:place",
        name="Choplet Ceramic Studio & Gallery",
    ),
    EntityRefOut(
        id="6E449EFE-6006-4023-8EEC-0F1F720BDC94", type="urn:entity:place", name="BKLYN CLAY"
    ),
    EntityRefOut(
        id="98F7EBDF-987C-4741-B6F8-5C7511DC0021", type="urn:entity:place", name="Kettl Tea"
    ),
]
AUSTIN_SEED = [
    EntityRefOut(id="32F867B9-E6DF-44C3-BCE4-40160C7ED5E4", type="urn:entity:brand", name="Aesop"),
    EntityRefOut(
        id="41C4BB40-E667-416F-9541-63FD7E7FFFF5", type="urn:entity:brand", name="Ilegal Mezcal"
    ),
    EntityRefOut(
        id="BAF6317A-DF94-4C90-92AE-63F86560C21B", type="urn:entity:artist", name="Khruangbin"
    ),
]
COLABA_SEED = [
    EntityRefOut(
        id="0DE2E903-CCB5-4523-BAF0-3EC15514248C",
        type="urn:entity:place",
        name="Mary Lodge by Subko",
    ),
    EntityRefOut(
        id="BC400638-8F5F-4F9C-9634-4833CA61E26F",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Colaba",
    ),
    EntityRefOut(
        id="6CEDF620-266F-4B72-B14E-875532C321B1",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Bandra",
    ),
    EntityRefOut(
        id="617683A6-DCF8-4104-8A1A-7484D1F9601C",
        type="urn:entity:place",
        name="Blue Tokai Coffee Roasters | Versova",
    ),
]

BROOKLYN = (40.7172, -73.9566)
AUSTIN = (30.2672, -97.7431)
COLABA = (18.93, 72.83)

CAFE = "urn:tag:genre:place:restaurant:cafe"
BAR = "urn:tag:genre:place:restaurant:bar"
GALLERY = "urn:tag:genre:place:art_gallery"
CERAMICS = "urn:tag:genre:place:ceramics"

ALPHA = "11111111-1111-4111-8111-111111111111"
BETA = "22222222-2222-4222-8222-222222222222"
GAMMA = "33333333-3333-4333-8333-333333333333"

EMPTY_DEMOGRAPHICS = {"results": {"demographics": []}}


def make_client(transport: Any) -> QlooClient:
    """A taste-layer client on the test settings, wired to a scripted transport."""
    return QlooClient(make_settings(), transport=transport)


def board(*rows: dict[str, Any]) -> dict[str, Any]:
    """A live-shaped place board payload (``results.entities``)."""
    return {"results": {"entities": list(rows)}}


def door_row(
    entity_id: str,
    name: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    affinity: float = 0.9,
    tags: tuple[tuple[str, str, str], ...] = (),
    contributions: tuple[tuple[str, float], ...] = (),
) -> dict[str, Any]:
    """One live-shaped place row for scripted transports."""
    row: dict[str, Any] = {
        "entity_id": entity_id,
        "name": name,
        "type": "urn:entity:place",
        "tags": [
            {"id": urn, "name": label, "type": kind, "weight": None} for urn, label, kind in tags
        ],
        "query": {"affinity": affinity},
    }
    if lat is not None:
        row["location"] = {"lat": lat, "lon": lon}
    if contributions:
        row["query"]["explainability"] = {
            "signal.interests.entities": [
                {"entity_id": entity, "score": score} for entity, score in contributions
            ]
        }
    return row


def profile_row(
    entity_id: str, ages: dict[str, float], *, male: float = 0.0, female: float = 0.0
) -> dict[str, Any]:
    """One live-shaped demographics row (nested under ``query``)."""
    return {
        "entity_id": entity_id,
        "query": {"age": ages, "gender": {"male": male, "female": female}},
    }


class OverlayTransport:
    """Fixture replay with a scripted queue for calls the pack never recorded.

    Tests use this when a call is deliberately unrecorded (for example the
    top-door demographics batch, which no preset contains). Recorded requests
    still replay from the locked pack; a scripted answer is consumed only
    after a fixture miss, and ``self.scripted`` records exactly which calls
    leaned on the script so the test can assert them.
    """

    name = "overlay"

    def __init__(self, pack: FixturePack, *script: TransportResponse | Exception) -> None:
        self._fixture = FixtureTransport(pack)
        self._script = list(script)
        self.scripted: list[tuple[str, list[tuple[str, str]]]] = []

    async def get(self, path: str, params: list[tuple[str, str]]) -> TransportResponse:
        try:
            return await self._fixture.get(path, params)
        except QlooFixtureMissError:
            if not self._script:
                raise
            self.scripted.append((path, list(params)))
            item = self._script.pop(0)
            if isinstance(item, Exception):
                raise item from None
            return item

    async def aclose(self) -> None:
        await self._fixture.aclose()


class SleepingClock:
    """A virtual clock whose sleeper advances time instead of blocking."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make_settings(**overrides: Any) -> Settings:
    """Settings for tests: fixture-capable, none of the pacing delays.

    Unknown overrides raise, so a helper bug (passing a client argument into
    settings) fails loudly instead of being silently ignored by the model.
    """
    unknown = set(overrides) - set(Settings.model_fields)
    if unknown:
        raise TypeError(f"unknown settings override(s): {sorted(unknown)}")
    base: dict[str, Any] = {
        "mode": "fixture",
        "qloo_api_key": "test-key-not-secret",
        "qloo_rps": 0.0,
        "qloo_backoff_base_seconds": 0.0,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)
