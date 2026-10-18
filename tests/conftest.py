"""Shared pytest fixtures for the service-taste tests.

Pack-dependent tests replay the redacted fixture pack from the adjacent
karum-infra checkout. CI checks out karum-infra and sets
``TASTE_REQUIRE_FIXTURES=1``, which turns the missing-pack skip into a failure
so a green run can never quietly lose its fixtures.
"""

from __future__ import annotations

import pytest

from karum_service_taste.qloo.fixtures import FixturePack
from support import MISSING_PACK_MESSAGE, REQUIRED, resolve_pack_dir


@pytest.fixture(scope="session")
def pack() -> FixturePack:
    """The redacted fixture pack; skips (or fails, in CI) when absent."""
    directory = resolve_pack_dir()
    if not (directory / "qloo").is_dir():
        message = MISSING_PACK_MESSAGE.format(directory=directory)
        if REQUIRED:
            pytest.fail(message)
        pytest.skip(message)
    return FixturePack(directory)
