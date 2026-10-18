"""Typed Qloo client (PLAN.md §7).

One method per verified endpoint and parameter set; the recipes and their
evidence live in the infra repo's ``QLOO_APIS.md``. Nothing unverified appears
here: no method for an endpoint the spike did not exercise, no default for a
parameter the recordings never sent.

Behaviour:

- timeouts, retries with exponential backoff, and honour of the
  ``X-Second-RateLimit-*`` / ``X-Month-RateLimit-*`` headers observed on every
  response (5/second and 10,000/month on the hackathon key, 18 Oct 2026);
- the API key rides a header and never appears in a URL, a log line, or an
  evidence record;
- timeouts, 429s, and 5xx map onto the shared taxonomy
  (:mod:`karum_service_taste.qloo.errors`);
- every call returns a typed response carrying rows, warnings, and a
  :class:`CallRecord` the evidence drawer can cite;
- ``Mode.FIXTURE`` serves the redacted pack
  (:mod:`karum_service_taste.qloo.fixtures`) with no network.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic import ValidationError

from karum_service_taste.core.config import Mode, Settings
from karum_service_taste.qloo import canonical
from karum_service_taste.qloo.errors import (
    ErrorCode,
    QlooPayloadError,
    QlooRateLimitedError,
    QlooTransportError,
    QlooValidationError,
    error_for_status,
    is_retryable_status,
)
from karum_service_taste.qloo.fixtures import FixturePack, FixtureTransport, resolve_fixtures_dir
from karum_service_taste.qloo.metrics import QlooMetrics
from karum_service_taste.qloo.models import (
    CallRecord,
    CatalogTag,
    CompareResponse,
    CompareRow,
    DemographicsResponse,
    DemographicsRow,
    HeatmapCell,
    HeatmapResponse,
    LocalityResponse,
    LocalityRow,
    PlaceRow,
    PlacesResponse,
    QlooResponse,
    QlooWarning,
    SearchEntity,
    SearchResponse,
    TagsResponse,
)
from karum_service_taste.qloo.ratelimit import Pacer, RateLimitSnapshot
from karum_service_taste.qloo.transport import HttpxTransport, Transport, TransportResponse

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]

_UUID_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)

#: Seed/tag calls cap their signal lists; four entities is the preset ceiling
#: (PLAN.md §26) and the widest recorded probe sent eight.
_MAX_SIGNAL_ENTITIES = 8


class QlooClient:
    """Async client for the hackathon Qloo surface.

    Args:
        settings: service settings. ``qloo_api_key`` is only ever handed to
            the live transport as a header.
        transport: overrides the mode-derived transport (tests pass fakes).
        sleep: injectable sleeper so retry/backoff tests run instantly.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        transport: Transport | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._sleep = sleep or asyncio.sleep
        self._metrics = QlooMetrics()
        self._last_rate_limit: RateLimitSnapshot | None = None
        rps = settings.qloo_rps
        self._pacer = Pacer(1.0 / rps if rps > 0 else 0.0, sleep=self._sleep)

    # -- introspection -----------------------------------------------------

    @property
    def base_url(self) -> str:
        """Qloo base URL, resolved from settings."""
        return self._settings.qloo_base_url

    @property
    def metrics(self) -> QlooMetrics:
        """Call counters and latency aggregates for health reporting."""
        return self._metrics

    @property
    def last_rate_limit(self) -> RateLimitSnapshot | None:
        """The most recent rate-limit headers seen, if any."""
        return self._last_rate_limit

    @property
    def transport_name(self) -> str:
        """The active transport's label (``fixture`` or ``httpx``).

        Mode-derived without building the transport, so health reporting
        never loads the fixture pack or opens a connection.
        """
        if self._transport is not None:
            return self._transport.name
        return "fixture" if self._settings.mode is Mode.FIXTURE else "httpx"

    def _transport_or_default(self) -> Transport:
        if self._transport is None:
            self._transport = self._build_transport()
        return self._transport

    def _build_transport(self) -> Transport:
        if self._settings.mode is Mode.FIXTURE:
            root = resolve_fixtures_dir(self._settings.fixtures_dir)
            return FixtureTransport(FixturePack(root))
        # Live and degraded both call Qloo; degraded only trims features
        # above this layer.
        return HttpxTransport(
            base_url=self._settings.qloo_base_url,
            api_key=self._settings.qloo_api_key,
            timeout_seconds=self._settings.qloo_timeout_seconds,
        )

    async def aclose(self) -> None:
        """Close the transport, if one was built."""
        if self._transport is not None:
            await self._transport.aclose()

    # -- verified endpoint methods ----------------------------------------

    async def search(
        self,
        query: str,
        *,
        types: Sequence[str] | None = None,
        take: int = 5,
        page: int | None = None,
        location: tuple[float, float] | None = None,
        radius_miles: float | None = None,
        sort_by: str | None = None,
    ) -> SearchResponse:
        """Resolve a name via ``GET /search`` (QLOO_APIS.md §3.1).

        ``location`` is a bare ``(lat, lon)`` pair — latitude first, and
        ``radius_miles`` is in **miles** (the unit trap; insights are metres).
        Leave ``sort_by`` unset for name lookups: ``distance`` means "nearest
        venues" (trap 7).
        """
        if not query or not query.strip():
            raise QlooValidationError("search query is empty", endpoint="search")
        params: list[tuple[str, str]] = [("query", query)]
        if types:
            params.append(("types", canonical.format_list(types)))
        params.append(("take", str(take)))
        if page is not None:
            params.append(("page", str(page)))
        if location is not None:
            params.append(("filter.location", canonical.format_pair(location[0], location[1])))
        if radius_miles is not None:
            params.append(("filter.radius", canonical.format_number(radius_miles)))
        if sort_by is not None:
            params.append(("sort_by", sort_by))
        return await self._call("search", "/search", params, _parse_search)  # type: ignore[return-value]

    async def tags(
        self,
        query: str,
        *,
        tag_types: Sequence[str] | None = None,
        take: int = 25,
    ) -> TagsResponse:
        """Resolve a chip via ``GET /v2/tags`` (QLOO_APIS.md §3.2)."""
        if not query or not query.strip():
            raise QlooValidationError("tag query is empty", endpoint="tags")
        params: list[tuple[str, str]] = [("filter.query", query)]
        if tag_types:
            params.append(("filter.tag.types", canonical.format_list(tag_types)))
        params.append(("take", str(take)))
        return await self._call("tags", "/v2/tags", params, _parse_tags)  # type: ignore[return-value]

    async def insights_places(
        self,
        entities: Sequence[str],
        *,
        location: tuple[float, float],
        radius_m: float,
        category_tags: Sequence[str] | None = None,
        interest_tags: Sequence[str] | None = None,
        results_entities: Sequence[str] | None = None,
        take: int = 25,
        explainability: bool = True,
    ) -> PlacesResponse:
        """The door-shaped place board via ``GET /v2/insights`` (§3.13).

        ``location`` is a ``(lat, lon)`` pair; the call formats WKT
        ``POINT(lon lat)`` (longitude first — DI-21) with an explicit metre
        radius (a point without radius returns zero rows). ``category_tags``
        narrow with ``filter.tags``; ``interest_tags`` widen the signal with
        ``signal.interests.tags``; ``results_entities`` restricts the result
        set (the skip-list batch probe). ``explainability=False`` omits the
        flag the way the skip probes recorded it.
        """
        ids = _clean_entities(entities, "insights.place")
        params: list[tuple[str, str]] = [
            ("filter.type", "urn:entity:place"),
            ("signal.interests.entities", canonical.format_list(ids)),
            ("filter.location", canonical.format_point(location[1], location[0])),
            ("filter.location.radius", canonical.format_number(radius_m)),
        ]
        if category_tags:
            params.append(("filter.tags", canonical.format_list(category_tags)))
        if interest_tags:
            params.append(("signal.interests.tags", canonical.format_list(interest_tags)))
        if results_entities:
            params.append(
                (
                    "filter.results.entities",
                    canonical.format_list(_clean_entities(results_entities, "insights.place")),
                )
            )
        params.append(("take", str(take)))
        if explainability:
            params.append(("feature.explainability", "true"))
        return await self._call(  # type: ignore[return-value]
            "insights.place", "/v2/insights", params, _parse_places
        )

    async def insights_heatmap(
        self,
        entities: Sequence[str],
        *,
        location: tuple[float, float],
        radius_m: float,
        boundary: str | None = None,
        take: int = 50,
    ) -> HeatmapResponse:
        """Heatmap cells via ``GET /v2/insights`` (§3.7).

        ``boundary`` stays unset for the default cell grid or takes the
        recorded ``urn:geohash`` variant; locality polygons have their own
        method so each returns one row type.
        """
        params = self._heatmap_params(
            entities, location=location, radius_m=radius_m, boundary=boundary, take=take
        )
        return await self._call(  # type: ignore[return-value]
            "insights.heatmap", "/v2/insights", params, _parse_heatmap
        )

    async def insights_localities(
        self,
        entities: Sequence[str],
        *,
        location: tuple[float, float],
        radius_m: float,
        take: int = 50,
    ) -> LocalityResponse:
        """Locality polygons via ``GET /v2/insights`` (§3.7, DI-12).

        ``output.heatmap.boundary=urn:entity:locality`` switches the container
        to entity rows whose ``boundary`` is a WKT MULTIPOLYGON string.
        """
        params = self._heatmap_params(
            entities,
            location=location,
            radius_m=radius_m,
            boundary="urn:entity:locality",
            take=take,
        )
        return await self._call(  # type: ignore[return-value]
            "insights.locality", "/v2/insights", params, _parse_localities
        )

    def _heatmap_params(
        self,
        entities: Sequence[str],
        *,
        location: tuple[float, float],
        radius_m: float,
        boundary: str | None,
        take: int,
    ) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("filter.type", "urn:heatmap"),
            (
                "signal.interests.entities",
                canonical.format_list(_clean_entities(entities, "insights.heatmap")),
            ),
            ("filter.location", canonical.format_point(location[1], location[0])),
            ("filter.location.radius", canonical.format_number(radius_m)),
            ("take", str(take)),
        ]
        if boundary:
            params.append(("output.heatmap.boundary", boundary))
        return params

    async def insights_demographics(
        self,
        entities: Sequence[str],
        *,
        results_entities: Sequence[str] | None = None,
        take: int | None = None,
    ) -> DemographicsResponse:
        """Per-entity profiles via ``GET /v2/insights`` (§3.6).

        ``filter.results.entities`` is sent when asked but the upstream
        ignores it (DI-25); rows follow the signal inputs, and coverage is
        partial — call per door for per-door profiles.
        """
        params: list[tuple[str, str]] = [
            ("filter.type", "urn:demographics"),
            (
                "signal.interests.entities",
                canonical.format_list(_clean_entities(entities, "insights.demographics")),
            ),
        ]
        if results_entities:
            params.append(
                (
                    "filter.results.entities",
                    canonical.format_list(
                        _clean_entities(results_entities, "insights.demographics")
                    ),
                )
            )
        if take is not None:
            params.append(("take", str(take)))
        return await self._call(  # type: ignore[return-value]
            "insights.demographics", "/v2/insights", params, _parse_demographics
        )

    async def compare(
        self,
        a_entity: str,
        b_entity: str,
        *,
        entity_type: str = "urn:entity:brand",
        take: int = 50,
    ) -> CompareResponse:
        """One door against a brand via ``GET /v2/analysis/compare`` (§3.10)."""
        for label, entity in (("a", a_entity), ("b", b_entity)):
            if not _UUID_RE.match(entity or ""):
                raise QlooValidationError(
                    f"compare side {label} is not an entity id: {entity!r}", endpoint="compare"
                )
        params: list[tuple[str, str]] = [
            ("a.signal.interests.entities", a_entity),
            ("b.signal.interests.entities", b_entity),
            ("filter.type", entity_type),
            ("take", str(take)),
        ]
        return await self._call("compare", "/v2/analysis/compare", params, _parse_compare)  # type: ignore[return-value]

    # -- the request pipeline ---------------------------------------------

    async def _call(
        self,
        endpoint: str,
        path: str,
        params: list[tuple[str, str]],
        parse: Callable[[Any], QlooResponse],
    ) -> QlooResponse:
        """One logical call: pace, retry, map failures, parse, record."""
        transport = self._transport_or_default()
        started = time.monotonic()
        attempts = 0
        max_attempts = max(1, self._settings.qloo_max_retries + 1)
        response: TransportResponse | None = None

        while True:
            await self._guard_month_budget(endpoint)
            attempts += 1
            await self._pacer.wait()
            try:
                response = await transport.get(path, params)
            except QlooTransportError as exc:
                if attempts < max_attempts:
                    delay = self._backoff(attempts)
                    logger.warning(
                        "qloo_retry",
                        extra={
                            "endpoint": endpoint,
                            "attempt": attempts,
                            "detail": exc.detail,
                            "backoff_s": delay,
                        },
                    )
                    await self._sleep(delay)
                    continue
                self._record_failure(endpoint, started, exc.error_code)
                raise QlooTransportError(
                    exc.detail, endpoint=endpoint, retry_after=exc.retry_after
                ) from exc

            snapshot = RateLimitSnapshot.from_headers(response.headers or {})
            if snapshot is not None:
                self._last_rate_limit = snapshot
                await self._honour_second_budget(snapshot)

            if response.status >= 400:
                retry_after = self._retry_after_for(response, snapshot)
                if attempts < max_attempts and is_retryable_status(response.status):
                    delay = max(self._backoff(attempts), retry_after)
                    logger.warning(
                        "qloo_retry",
                        extra={
                            "endpoint": endpoint,
                            "attempt": attempts,
                            "status": response.status,
                            "backoff_s": delay,
                        },
                    )
                    await self._sleep(delay)
                    continue
                error = error_for_status(
                    response.status,
                    f"Qloo returned HTTP {response.status} for {path}",
                    endpoint=endpoint,
                    retry_after=retry_after or None,
                )
                self._record_failure(endpoint, started, error.error_code)
                raise error

            break

        assert response is not None  # the loop only exits on a response
        try:
            result = parse(response.payload)
        except QlooPayloadError as exc:
            self._record_failure(endpoint, started, exc.error_code)
            exc.endpoint = endpoint
            raise

        total_ms = (time.monotonic() - started) * 1000
        rows_count = _primary_row_count(result)
        result.call = CallRecord(
            endpoint=endpoint,
            path=path,
            parameters=canonical.format_params(params),
            status=response.status,
            duration_ms=round(total_ms, 3),
            attempts=attempts,
            rows=rows_count,
            rate_limit=self._last_rate_limit,
        )
        self._metrics.record_call(endpoint, duration_ms=total_ms, rows=rows_count)
        logger.debug(
            "qloo_call",
            extra={
                "endpoint": endpoint,
                "path": path,
                "parameters": result.call.parameters,
                "status": response.status,
                "rows": rows_count,
                "duration_ms": result.call.duration_ms,
                "attempts": attempts,
            },
        )
        return result

    def _record_failure(self, endpoint: str, started: float, code: ErrorCode) -> None:
        self._metrics.record_call(endpoint, duration_ms=(time.monotonic() - started) * 1000)
        self._metrics.record_error(endpoint, code)

    async def _guard_month_budget(self, endpoint: str) -> None:
        snapshot = self._last_rate_limit
        if snapshot is None or snapshot.month_remaining is None or snapshot.month_remaining > 0:
            return
        raise QlooRateLimitedError(
            "monthly Qloo budget exhausted; wait for X-Month-RateLimit-Reset",
            endpoint=endpoint,
            retry_after=snapshot.month_reset,
        )

    async def _honour_second_budget(self, snapshot: RateLimitSnapshot) -> None:
        if snapshot.second_remaining == 0 and snapshot.second_reset:
            await self._pacer.hold(snapshot.second_reset)

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff: base, 2x base, 4x base, … (attempt is 1-based)."""
        return self._settings.qloo_backoff_base_seconds * (2 ** (attempt - 1))

    @staticmethod
    def _retry_after_for(response: TransportResponse, snapshot: RateLimitSnapshot | None) -> float:
        for key, value in (response.headers or {}).items():
            if key.lower() == "retry-after":
                try:
                    return max(0.0, float(value))
                except ValueError:
                    break
        if snapshot is not None and snapshot.second_reset is not None:
            return max(0.0, snapshot.second_reset)
        return 0.0


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _clean_entities(entities: Sequence[str], endpoint: str) -> list[str]:
    """Trim and check entity ids before anything is sent upstream."""
    cleaned = [entity.strip() for entity in entities if entity and entity.strip()]
    if not cleaned:
        raise QlooValidationError("no entity ids given", endpoint=endpoint)
    if len(cleaned) > _MAX_SIGNAL_ENTITIES:
        raise QlooValidationError(
            f"{len(cleaned)} entity ids exceed the recorded breadth of {_MAX_SIGNAL_ENTITIES}",
            endpoint=endpoint,
        )
    for entity in cleaned:
        if not _UUID_RE.match(entity):
            raise QlooValidationError(
                f"entity id is not a Qloo UUID: {entity!r}", endpoint=endpoint
            )
    return cleaned


def _validate_rows(model: type, rows: Sequence[Any], label: str) -> list[Any]:
    try:
        return [model.model_validate(row) for row in rows]
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        raise QlooPayloadError(
            f"{label} row failed validation at {location or '<root>'}: {first.get('msg')}"
        ) from exc


def _parse_warnings(payload: Any) -> list[QlooWarning]:
    raw: Any = None
    if isinstance(payload, dict):
        raw = payload.get("warnings")
        results = payload.get("results")
        if raw is None and isinstance(results, dict):
            raw = results.get("warnings")
    warnings: list[QlooWarning] = []
    for item in raw or []:
        if isinstance(item, dict):
            warnings.append(QlooWarning.model_validate(item))
    return warnings


def _rows_at(payload: Any, *path: str) -> list[Any]:
    node = payload
    for part in path:
        if not isinstance(node, dict) or part not in node:
            raise QlooPayloadError(f"payload has no {'.'.join(path)}")
        node = node[part]
    if not isinstance(node, list):
        raise QlooPayloadError(f"{'.'.join(path)} is not a list")
    return [row for row in node if isinstance(row, dict)]


# ---------------------------------------------------------------------------
# Payload parsers; each one mirrors the live container shape.
# ---------------------------------------------------------------------------


def _parse_search(payload: Any) -> SearchResponse:
    results = payload.get("results") if isinstance(payload, dict) else None
    if isinstance(results, dict):
        results = results.get("entities")
    if not isinstance(results, list):
        raise QlooPayloadError("payload has no results list")
    rows = [row for row in results if isinstance(row, dict)]
    return SearchResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(SearchEntity, rows, "search"),
    )


def _parse_tags(payload: Any) -> TagsResponse:
    return TagsResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(CatalogTag, _rows_at(payload, "results", "tags"), "tags"),
    )


def _parse_places(payload: Any) -> PlacesResponse:
    return PlacesResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(PlaceRow, _rows_at(payload, "results", "entities"), "place"),
    )


def _parse_heatmap(payload: Any) -> HeatmapResponse:
    return HeatmapResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(HeatmapCell, _rows_at(payload, "results", "heatmap"), "heatmap cell"),
    )


def _parse_localities(payload: Any) -> LocalityResponse:
    return LocalityResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(LocalityRow, _rows_at(payload, "results", "entities"), "locality"),
    )


def _parse_demographics(payload: Any) -> DemographicsResponse:
    return DemographicsResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(
            DemographicsRow, _rows_at(payload, "results", "demographics"), "demographics"
        ),
    )


def _parse_compare(payload: Any) -> CompareResponse:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, dict) or not any(
        key in results for key in ("a", "b", "matchEntities")
    ):
        raise QlooPayloadError("payload has no compare sides")

    def side(key: str) -> list[Any]:
        node = results.get(key)
        return [row for row in node if isinstance(row, dict)] if isinstance(node, list) else []

    return CompareResponse(
        warnings=_parse_warnings(payload),
        rows=_validate_rows(CompareRow, side("tags"), "compare.tags"),
        a=_validate_rows(CompareRow, side("a"), "compare.a"),
        b=_validate_rows(CompareRow, side("b"), "compare.b"),
        match_entities=_validate_rows(CompareRow, side("matchEntities"), "compare.matchEntities"),
    )


def _primary_row_count(response: QlooResponse) -> int:
    if isinstance(response, CompareResponse):
        return len(response.a)
    rows = getattr(response, "rows", None)
    return len(rows) if isinstance(rows, list) else 0
