"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from karum_service_taste.main import app


def test_health_returns_ok() -> None:
    """GET /health should report the service name, status, and mode."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "service-taste"
    assert body["status"] == "ok"
    # Default mode with no env overrides is fixture.
    assert body["mode"] == "fixture"


def test_health_includes_uptime_and_timestamp() -> None:
    """The health payload should carry uptime and a UTC timestamp."""
    with TestClient(app) as client:
        body = client.get("/health").json()

    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0
    # ISO-8601 timestamp, terminated with Z for UTC.
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
