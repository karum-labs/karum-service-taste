"""The API key never reaches logs, URLs, or error text (PLAN.md §7)."""

from __future__ import annotations

import logging

import httpx
import pytest

from karum_service_taste.core.logging import RedactingFilter
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.transport import HttpxTransport
from support import FakeTransport, make_settings, ok

SECRET = "qloo-secret-key-abc123"


def test_redacting_filter_blanks_credential_attributes() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hi", (), None)
    record.api_key = SECRET
    record.endpoint = "search"
    RedactingFilter().filter(record)
    assert record.api_key == "[REDACTED]"
    assert record.endpoint == "search"


async def test_httpx_transport_sends_the_key_as_a_header_not_a_url() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    inner = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    transport = HttpxTransport(
        base_url="https://hackathon.api.qloo.com",
        api_key=SECRET,
        timeout_seconds=5.0,
        client=inner,
    )
    response = await transport.get("/search", [("query", "Aesop")])
    assert response.status == 200
    request = seen[0]
    assert request.headers["X-Api-Key"] == SECRET
    assert SECRET not in str(request.url)
    await transport.aclose()


async def test_client_logs_never_contain_the_key(caplog: pytest.LogCaptureFixture) -> None:
    transport = FakeTransport(ok({"results": []}))
    client = QlooClient(make_settings(qloo_api_key=SECRET), transport=transport)
    with caplog.at_level(logging.DEBUG):
        await client.search("Aesop")
    assert SECRET not in caplog.text
    assert "qloo_call" in caplog.text
