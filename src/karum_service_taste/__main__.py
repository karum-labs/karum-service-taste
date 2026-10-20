"""Process entrypoint for service-taste.

Runs the HTTP app on ``TASTE_PORT`` and starts the gRPC server beside it, so
the port the container publishes and the port the settings carry are the same
number. ``python -m karum_service_taste`` is the container command;
``uvicorn karum_service_taste.main:app`` still works for a local run.
"""

from __future__ import annotations

import uvicorn

from karum_service_taste.core.config import get_settings
from karum_service_taste.main import app


def main() -> None:
    """Serve the app on the configured port."""
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
