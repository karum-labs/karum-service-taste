"""Health endpoint for service-taste.

``GET /health`` is the single probe that Compose, Cloud Run, and the uptime
check point at. It reports the service's operational mode so a fixture or
degraded run is visible to the client banner, plus the Qloo client's transport
and call metrics so the judging dashboard can see what the service has done
without scraping logs (PLAN.md §7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()

# Process start time, used to compute uptime. Set at import so every health
# response reports a stable figure.
_STARTED = monotonic()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Return service identity, status, operational mode, and Qloo activity."""
    settings = request.app.state.settings
    client = request.app.state.qloo
    rate_limit = client.last_rate_limit
    return {
        "service": settings.service_name,
        "status": "ok",
        "mode": settings.mode.value,
        "uptime_seconds": int(monotonic() - _STARTED),
        "time": datetime.now(UTC).isoformat(),
        "qloo": {
            "transport": client.transport_name,
            "metrics": client.metrics.snapshot(),
            "rate_limit": rate_limit.model_dump() if rate_limit is not None else None,
        },
    }
