"""FastAPI application factory for service-taste.

Creates the ASGI app, wires routes, and configures logging. The gRPC server that
the gateway dials will be started alongside this app in a later pass; for now the
HTTP surface exposes ``/health`` so the service is probeable by Compose and
Cloud Run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from karum_service_taste import __version__
from karum_service_taste.api.routes import health
from karum_service_taste.core.cache import build_cache
from karum_service_taste.core.config import get_settings
from karum_service_taste.core.logging import configure as configure_logging
from karum_service_taste.qloo import QlooClient


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release the Qloo transport (if one was ever built) on shutdown."""
    yield
    await app.state.qloo.aclose()


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Settings are read once at import so the health endpoint and any future
    handlers share a single cached configuration.
    """
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Karum service-taste",
        description="Qloo integration, caching, and taste scoring for the Karum tenant-mix leasing agent.",
        version=__version__,
        # The service is called by the gateway, not browsed directly, so the
        # auto-generated docs are only useful in local development.
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Expose the resolved settings and the shared Qloo client on the app state
    # so handlers and tests can reach them without re-reading the environment.
    # The client is cheap to construct: its transport (fixture pack or httpx)
    # and its cache (Redis primary, in-memory fallback) are built lazily.
    app.state.settings = settings
    app.state.qloo = QlooClient(
        settings, cache=build_cache(settings.redis_addr, ttl_seconds=settings.cache_ttl_seconds)
    )
    app.state.cache = app.state.qloo.cache

    app.include_router(health.router)

    return app


# Module-level ASGI entrypoint. ``uvicorn karum_service_taste.main:app`` works
# out of the box, and the gRPC server can import :func:`create_app` directly.
app = create_app()
