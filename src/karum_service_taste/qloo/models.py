"""Typed payload models for the Qloo endpoints Karum calls.

Every model mirrors the live Taste Graph payload nesting, and where the
redacted fixture pack flattens a value (``project_*`` in
``fixtures/tools/redact.py``) the model accepts both spellings so one parser
path serves live calls and fixture replay alike. Records are rebuildable in
both directions because redaction keeps exactly the consume-list.

Coverage rule (PLAN.md §7): models exist only for endpoints and parameters the
spike verified — there is deliberately no model for an unverified surface.

Unit conventions (QLOO_APIS.md §3): locations inside rows are WGS-84 decimal
degrees; ``distance`` is metres; heatmap ``affinity_rank`` is the within-cell
percentile Qloo publishes.
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from karum_service_taste.qloo.ratelimit import RateLimitSnapshot


class QlooModel(BaseModel):
    """Base model: tolerate unknown upstream fields, keep names predictable."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class GeoPoint(QlooModel):
    """A WGS-84 point; accepts both ``lat``/``lon`` and ``latitude``/``longitude``."""

    lat: float = Field(validation_alias=AliasChoices("lat", "latitude"))
    lon: float = Field(validation_alias=AliasChoices("lon", "longitude"))


class Geocode(QlooModel):
    """The geocoded address Qloo returns beside a place (DR-2 collision check)."""

    city: str | None = None
    name: str | None = None
    metro: str | None = None
    country: str | None = None
    admin1_region: str | None = None


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------


class SearchEntity(QlooModel):
    """One row of ``GET /search`` (brand, place, or artist)."""

    entity_id: str
    name: str
    types: list[str] = Field(default_factory=list)
    location: GeoPoint | None = None
    disambiguation: str | None = None
    geocode: Geocode | None = None

    @model_validator(mode="before")
    @classmethod
    def _lift_properties(cls, data: Any) -> Any:
        """Live rows nest the geocode under ``properties``; the pack lifts it."""
        if not isinstance(data, dict):
            return data
        if data.get("geocode") is None:
            properties = data.get("properties")
            if isinstance(properties, dict) and properties.get("geocode") is not None:
                data = {**data, "geocode": properties["geocode"]}
        return data


# ---------------------------------------------------------------------------
# /v2/tags
# ---------------------------------------------------------------------------


class CatalogTag(QlooModel):
    """One row of ``GET /v2/tags`` (the chip resolver's catalogue)."""

    id: str
    name: str
    type: str | None = None


# ---------------------------------------------------------------------------
# /v2/insights — place rows, cells, localities, demographics
# ---------------------------------------------------------------------------


class EntityTag(QlooModel):
    """A tag row carried on an entity payload."""

    id: str
    name: str
    type: str | None = None
    weight: float | None = None


class HoursInterval(QlooModel):
    """One open/close interval inside ``properties.hours[<weekday>]``."""

    opens: str | None = None
    closed: bool = False
    closes: str | None = None


class PriceRange(QlooModel):
    """``properties.price_range`` observed shape ``{from, to, currency}``."""

    from_: float | None = Field(default=None, alias="from")
    to: float | None = None
    currency: str | None = None


class PlaceProperties(QlooModel):
    """The consume-list of place ``properties`` (redaction keeps this block)."""

    address: str | None = None
    business_rating: float | None = None
    geocode: Geocode | None = None
    good_for: list[EntityTag] = Field(default_factory=list)
    hours: dict[str, list[HoursInterval]] = Field(default_factory=dict)
    is_closed: bool | None = None
    phone: str | None = None
    price_level: int | None = None
    price_range: PriceRange | None = None
    website: str | None = None

    @field_validator("good_for", mode="before")
    @classmethod
    def _good_for_list(cls, value: Any) -> Any:
        """Live rows sometimes carry a string here; it is not a card field."""
        return value if isinstance(value, list) else []

    @field_validator("hours", mode="before")
    @classmethod
    def _hours_dict(cls, value: Any) -> Any:
        """A closed or unknown venue can send ``null`` instead of a map."""
        return value if isinstance(value, dict) else {}


class SignalContribution(QlooModel):
    """One seed entity's score inside an explainability block."""

    entity_id: str
    score: float


class QueryTerms(QlooModel):
    """Scoring terms Qloo publishes on an insights row."""

    affinity: float | None = None
    distance: float | None = None
    #: Keyed by signal name, e.g. ``signal.interests.entities``.
    explainability: dict[str, list[SignalContribution]] | None = None


class PlaceRow(QlooModel):
    """One ranked place row from an insights call (the door board row)."""

    entity_id: str
    name: str
    type: str | None = None
    subtype: str | None = None
    disambiguation: str | None = None
    location: GeoPoint | None = None
    popularity: float | None = None
    tags: list[EntityTag] = Field(default_factory=list)
    query: QueryTerms = Field(default_factory=QueryTerms)
    properties: PlaceProperties = Field(default_factory=PlaceProperties)


class HeatmapCell(QlooModel):
    """One heatmap cell; live rows nest values under ``location``/``query``."""

    location: GeoPoint | None = None
    geohash: str | None = None
    affinity: float | None = None
    affinity_rank: float | None = None
    popularity: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        query = data.get("query")
        if isinstance(query, dict):
            for key in ("affinity", "affinity_rank", "popularity"):
                if data.get(key) is None and query.get(key) is not None:
                    data[key] = query[key]
        location = data.get("location")
        if isinstance(location, dict) and data.get("geohash") is None:
            data["geohash"] = location.get("geohash")
        return data


class LocalityRow(QlooModel):
    """One locality polygon row (``output.heatmap.boundary=urn:entity:locality``)."""

    entity_id: str
    name: str
    disambiguation: str | None = None
    affinity: float | None = None
    #: WKT MULTIPOLYGON string as Qloo publishes it (longitude latitude pairs).
    boundary: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _lift_affinity(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        query = data.get("query")
        if isinstance(query, dict) and data.get("affinity") is None:
            data = {**data, "affinity": query.get("affinity")}
        return data


class DemographicsRow(QlooModel):
    """One per-entity demographics profile; live rows nest under ``query``."""

    entity_id: str
    age: dict[str, float] = Field(default_factory=dict)
    gender: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _lift(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        query = data.get("query")
        if isinstance(query, dict):
            data = dict(data)
            for key in ("age", "gender"):
                if data.get(key) is None and isinstance(query.get(key), dict):
                    data[key] = query[key]
        return data


# ---------------------------------------------------------------------------
# /v2/analysis/compare
# ---------------------------------------------------------------------------


class CompareRow(QlooModel):
    """One shared-tag row of a compare payload (``results.a`` and friends)."""

    tag_id: str
    name: str
    type: str | None = None
    subtype: str | None = None
    entity_id: str
    count: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _lift_count(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("count") is None:
            query = data.get("query")
            if isinstance(query, dict) and query.get("count") is not None:
                data = {**data, "count": query["count"]}
        return data

    @field_validator("count", mode="before")
    @classmethod
    def _stringify(cls, value: Any) -> Any:
        """The API publishes counts as strings ("1"); keep them verbatim."""
        return None if value is None else str(value)


# ---------------------------------------------------------------------------
# Warnings and call records
# ---------------------------------------------------------------------------


class QlooWarning(QlooModel):
    """One entry of the upstream ``warnings`` array (e.g. a not-found signal)."""

    type: str = "unknown"
    missing_entities: list[str] = Field(default_factory=list, alias="signal.interests.entities")


class CallRecord(QlooModel):
    """One outbound call, recorded for metrics and the evidence drawer."""

    endpoint: str
    method: str = "GET"
    path: str
    #: Canonical, redaction-safe parameters (never the API key).
    parameters: str
    status: int
    duration_ms: float
    attempts: int
    rows: int
    rate_limit: RateLimitSnapshot | None = None
    #: True when the call was served from the cache and never reached Qloo.
    cache_hit: bool = False


class QlooResponse(QlooModel):
    """Base for every typed response: rows plus provenance."""

    warnings: list[QlooWarning] = Field(default_factory=list)
    call: CallRecord | None = None


class SearchResponse(QlooResponse):
    rows: list[SearchEntity] = Field(default_factory=list)


class TagsResponse(QlooResponse):
    rows: list[CatalogTag] = Field(default_factory=list)


class PlacesResponse(QlooResponse):
    rows: list[PlaceRow] = Field(default_factory=list)


class HeatmapResponse(QlooResponse):
    rows: list[HeatmapCell] = Field(default_factory=list)


class LocalityResponse(QlooResponse):
    rows: list[LocalityRow] = Field(default_factory=list)


class DemographicsResponse(QlooResponse):
    rows: list[DemographicsRow] = Field(default_factory=list)


class CompareResponse(QlooResponse):
    """Compare payload: ``rows`` is the ``results.tags`` overlap; sides and matches follow."""

    rows: list[CompareRow] = Field(default_factory=list)
    a: list[CompareRow] = Field(default_factory=list)
    b: list[CompareRow] = Field(default_factory=list)
    match_entities: list[CompareRow] = Field(default_factory=list)
