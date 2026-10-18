"""Transports for the Qloo client (PLAN.md §7).

A transport turns ``GET path?params`` into ``(status, headers, payload)``.
:class:`HttpxTransport` is the live path; the fixture transport
(:mod:`karum_service_taste.qloo.fixtures`) serves the redacted recordings with
no network. Transports stay thin: retries, pacing, and error mapping belong to
the client, so a fake transport is trivial to write in tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from karum_service_taste.qloo.errors import QlooTransportError


@dataclass(frozen=True)
class TransportResponse:
    """One raw upstream answer."""

    status: int
    headers: Mapping[str, str]
    payload: Any


@runtime_checkable
class Transport(Protocol):
    """One GET against the Qloo surface."""

    #: Short label for logs, e.g. ``httpx`` or ``fixture``.
    name: str

    async def get(self, path: str, params: Sequence[tuple[str, str]]) -> TransportResponse:
        """Issue the call and return the raw answer."""
        ...

    async def aclose(self) -> None:
        """Release any resources the transport holds."""
        ...


class HttpxTransport:
    """The live transport: one pooled :class:`httpx.AsyncClient`.

    The API key rides the ``X-Api-Key`` header (QLOO_APIS.md §1) and never
    appears in URLs, logs, or evidence records.
    """

    name = "httpx"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        # Headers ride every request instead of the client defaults, so an
        # injected client (tests, future pooling) still carries the key.
        self._headers = {"Accept": "application/json"}
        if api_key:
            self._headers["X-Api-Key"] = api_key
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
        )

    async def get(self, path: str, params: Sequence[tuple[str, str]]) -> TransportResponse:
        try:
            response = await self._client.get(path, params=list(params), headers=self._headers)
        except httpx.TimeoutException as exc:
            raise QlooTransportError(f"timeout: {exc!r}") from exc
        except httpx.TransportError as exc:
            raise QlooTransportError(f"transport failure: {exc!r}") from exc

        payload: Any = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = None
        return TransportResponse(
            status=response.status_code,
            headers=dict(response.headers),
            payload=payload,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
