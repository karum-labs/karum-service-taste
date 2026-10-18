"""Environment-driven configuration for service-taste.

Every variable read here is documented in the infra repo's ``.env.example``,
along with the process that reads it. Defaults are chosen so the service boots
in fixture mode with no ``.env`` file present.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    """How the service is currently operating.

    Mirrors the gateway's mode so ``/health`` payloads are consistent across the
    stack.
    """

    LIVE = "live"
    FIXTURE = "fixture"
    DEGRADED = "degraded"


class Settings(BaseSettings):
    """Settings for service-taste, loaded from the environment."""

    # pydantic-settings reads case-insensitively from env vars with no prefix
    # stripped, so TASTE_PORT maps to :mod:`port <port>`.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service identity -----------------------------------------------------
    #: gRPC port the taste service listens on.
    port: int = 8081
    #: Operational mode reported on /health.
    mode: Mode = Mode.FIXTURE
    #: Human-readable service name used in logs and health payloads.
    service_name: str = "service-taste"

    # Qloo ----------------------------------------------------------------
    #: Qloo API key. Injected via secret manager in production; never logged.
    qloo_api_key: str = ""
    #: Qloo base URL. The hackathon key only works against the hackathon host.
    qloo_base_url: str = "https://hackathon.api.qloo.com"
    #: Per-request timeout for outbound Qloo calls.
    qloo_timeout_seconds: float = 10.0
    #: Maximum retries with backoff for retriable Qloo failures.
    qloo_max_retries: int = 3
    #: Per-second request budget; the hackathon key publishes 5 via
    #: X-Second-RateLimit-Limit and the client paces itself below it.
    qloo_rps: float = 5.0
    #: Base seconds for exponential retry backoff (0.5, 1, 2, ...).
    qloo_backoff_base_seconds: float = 0.5
    #: Redacted fixture pack root, used in fixture mode. Relative paths
    #: resolve against this repository's root; the pack ships in karum-infra.
    fixtures_dir: Path = Path("../karum-infra/fixtures")

    # Cache ---------------------------------------------------------------
    #: Redis connection address. When empty the service uses an in-process cache.
    redis_addr: str = "localhost:6379"
    #: Time-to-live for cached Qloo responses, in seconds (24h default).
    cache_ttl_seconds: int = 24 * 60 * 60
    #: Maximum parallel outbound Qloo calls per block-profile request.
    fanout_cap: int = 4

    # Logging -------------------------------------------------------------
    #: Log level name.
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, cached after the first call."""
    return Settings()
