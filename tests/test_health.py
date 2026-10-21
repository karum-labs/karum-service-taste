"""Tests for the /health endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from karum_service_taste.api.routes import health
from karum_service_taste.core.config import Mode, Settings
from karum_service_taste.main import app
from karum_service_taste.qloo import QlooClient


def _health_body(settings: Settings) -> dict[str, Any]:
    """One GET /health against an app holding these settings (S-06)."""
    probe = FastAPI()
    probe.state.settings = settings
    probe.state.qloo = QlooClient(settings)
    probe.state.cache = None
    probe.include_router(health.router)
    with TestClient(probe) as client:
        response = client.get("/health")
    assert response.status_code == 200
    return response.json()


def test_health_returns_ok() -> None:
    """GET /health should report the service name, status, and mode."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "service-taste"
    assert body["status"] == "ok"
    # Default mode with no env overrides is fixture, and the recorded pack
    # ships beside the service, so the default app reports ok.
    assert body["mode"] == "fixture"


def test_health_includes_uptime_and_timestamp() -> None:
    """The health payload should carry uptime and a UTC timestamp."""
    with TestClient(app) as client:
        body = client.get("/health").json()

    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0
    # ISO-8601 timestamp, terminated with +00:00 for UTC.
    assert body["time"].endswith("+00:00")


def test_health_reports_the_qloo_transport_and_metrics() -> None:
    """The health payload should expose the Qloo transport and call metrics."""
    with TestClient(app) as client:
        body = client.get("/health").json()

    qloo = body["qloo"]
    # Default mode is fixture, so the pack transport is in play, not network.
    assert qloo["transport"] == "fixture"
    assert qloo["metrics"] == {}
    assert qloo["rate_limit"] is None


def test_health_reports_degraded_without_the_fixture_pack(tmp_path: Path) -> None:
    """Fixture mode with no pack reports degraded, not a false ok (S-06)."""
    body = _health_body(Settings(mode=Mode.FIXTURE, fixtures_dir=tmp_path / "no-pack"))

    assert body["status"] == "degraded"
    assert body["mode"] == "fixture"


def test_health_reports_degraded_in_live_mode_without_a_key() -> None:
    """Live mode with no Qloo key reports degraded: every call would 401 (S-06)."""
    body = _health_body(Settings(mode=Mode.LIVE, qloo_api_key=""))

    assert body["status"] == "degraded"
    assert body["mode"] == "live"


def test_health_reports_ok_in_live_mode_with_a_key() -> None:
    """Live mode with a Qloo key is serviceable, so the status stays ok (S-06)."""
    body = _health_body(Settings(mode=Mode.LIVE, qloo_api_key="hackathon-key"))

    assert body["status"] == "ok"
    assert body["mode"] == "live"
