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
from karum_service_taste.qloo.errors import QlooFixtureMissError
from karum_service_taste.qloo.fixtures import (
    REPO_ROOT,
    FixturePack,
    FixtureTransport,
    resolve_fixtures_dir,
)
from karum_service_taste.qloo.transport import TransportResponse

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
