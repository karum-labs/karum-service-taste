"""Logging setup for service-taste.

Logs are emitted as single plain-text lines (timestamp, level, logger name,
message) that Cloud Run and the judging-window dashboard can filter. The Qloo
API key is never written to a log line; see :func:`configure`.
"""

from __future__ import annotations

import logging
import sys

from karum_service_taste.core.config import get_settings

# Attribute names that must never appear in a log record, even if a caller
# passes them by mistake. Values under these keys are redacted.
_REDACTED_KEYS = frozenset(
    {
        "api_key",
        "x_api_key",
        "qloo_api_key",
        "authorization",
        "credentials",
        "service_account",
        "token",
        "secret",
    }
)


class RedactingFilter(logging.Filter):
    """Redact secret-looking attributes from log records.

    Qloo authentication is a simple ``X-Api-Key`` header. A committed or logged
    key is a real cost, so this filter defensively blanks any attribute whose
    name looks like a credential before the record reaches the handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # ``record.__dict__`` holds the structured attributes attached via the
        # ``extra=`` kwarg on logging calls.
        for key in list(record.__dict__):
            if key.lower() in _REDACTED_KEYS:
                record.__dict__[key] = "[REDACTED]"
        return True


def configure() -> None:
    """Install the logging configuration honouring the ``LOG_LEVEL`` setting.

    Idempotent: safe to call more than once (for example from tests).
    """
    settings = get_settings()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
