"""Karum service-taste: Qloo integration, caching, and taste scoring.

This microservice isolates Qloo's API quirks, authentication, and rate limits
from the rest of the system. The gateway calls it over gRPC; it exposes the
taste and scoring RPCs defined in the shared protos.
"""

__version__ = "0.1.0"
