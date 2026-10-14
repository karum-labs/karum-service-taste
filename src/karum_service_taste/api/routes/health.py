"""Health endpoint for service-taste.

``GET /health`` is the single probe that Compose, Cloud Run, and the uptime
check point at. It reports the service's operational mode so a fixture or
degraded run is visible to the client banner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import APIRouter

from karum_service_taste.core.config import get_settings

router = APIRouter()

# Process start time, used to compute uptime. Set at import so every health
# response reports a stable figure.
_STARTED = monotonic()


@router.get("/health")
def health() -> dict[str, Any]:
    """Return service identity, status, and operational mode."""
    settings = get_settings()
    return {
        "service": settings.service_name,
        "status": "ok",
        "mode": settings.mode.value,
        "uptime_seconds": int(monotonic() - _STARTED),
        "time": datetime.now(UTC).isoformat(),
    }
