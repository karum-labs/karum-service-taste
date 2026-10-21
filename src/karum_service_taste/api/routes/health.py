"""Health endpoint for service-taste.

``GET /health`` is the single probe that Compose, Cloud Run, and the uptime
check point at. It reports the service's operational mode so a fixture or
degraded run is visible to the client banner, plus the Qloo client's transport
and call metrics so the judging dashboard can see what the service has done
without scraping logs (PLAN.md §7). The status is an honest read of whether
the configured transport can serve: a missing fixture pack or Qloo key reports
``degraded`` instead of a hardcoded ``ok`` (S-06), while the HTTP status stays
200 so liveness probes do not fail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import APIRouter, Request

from karum_service_taste.core.config import Settings
from karum_service_taste.qloo import QlooClient
from karum_service_taste.qloo.fixtures import PACK_SUBDIR, resolve_fixtures_dir

router = APIRouter()

# Process start time, used to compute uptime. Set at import so every health
# response reports a stable figure.
_STARTED = monotonic()


def _status(settings: Settings, client: QlooClient) -> str:
    """``degraded`` when the active transport cannot serve, else ``ok``.

    The fixture transport needs the recorded pack; the live transport needs a
    Qloo API key. An injected transport (tests, embedding) is taken at face
    value. Nothing here loads the pack or opens a connection.
    """
    transport = client.transport_name
    if transport == "fixture":
        pack = resolve_fixtures_dir(settings.fixtures_dir) / PACK_SUBDIR
        return "ok" if pack.is_dir() else "degraded"
    if transport == "httpx":
        return "ok" if settings.qloo_api_key else "degraded"
    return "ok"


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Return service identity, status, operational mode, and Qloo activity."""
    settings = request.app.state.settings
    client = request.app.state.qloo
    rate_limit = client.last_rate_limit
    cache = request.app.state.cache
    return {
        "service": settings.service_name,
        "status": _status(settings, client),
        "mode": settings.mode.value,
        "uptime_seconds": int(monotonic() - _STARTED),
        "time": datetime.now(UTC).isoformat(),
        "qloo": {
            "transport": client.transport_name,
            "metrics": client.metrics.snapshot(),
            "rate_limit": rate_limit.model_dump() if rate_limit is not None else None,
        },
        "cache": {
            "backend": cache.backend_name if cache is not None else "none",
            "degraded": client.cache_degraded,
        },
    }
