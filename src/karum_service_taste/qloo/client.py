"""Qloo HTTP client for service-taste.

This is a skeleton. The real client exposes **one typed method per endpoint the
coverage spike verified** and deliberately has no method for an unverified
parameter. It will:

- set timeouts and retries with backoff,
- honour Qloo rate-limit response headers,
- redact the API key from every log line,
- map timeouts, 429s, and 5xx responses onto the shared proto error codes.

Replay tests load the redacted fixture pack and assert the typed structs with no
live network. See PLAN.md epic 3 for the full contract.
"""

from __future__ import annotations

from karum_service_taste.core.config import Settings


class QlooClient:
    """Typed client for the Qloo Taste Graph API.

    A placeholder that holds configuration and performs no network calls. Each
    method will be added only once the spike confirms the corresponding endpoint
    is enabled on the hackathon key.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def base_url(self) -> str:
        """Qloo base URL, resolved from settings."""
        return self._settings.qloo_base_url

    # TODO(spike): confirm which of search, tags, insights, heatmap, and compare
    # the hackathon key may call, then add one typed method per verified endpoint.
    #
    # TODO(resolve): search_places(query, city) -> list[Entity]
    # TODO(resolve): search_brands(query) -> list[Entity]
    # TODO(tags):    resolve_tags(phrase) -> list[TagUrn]
    # TODO(profile): insights(entity_ids, location) -> Insights
