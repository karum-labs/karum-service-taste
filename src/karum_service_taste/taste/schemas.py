"""Result schemas for the taste resolution layer.

These mirror the frozen protos in ``karum-infra/proto/karum/taste/v1`` closely
enough that the gRPC servicer is a field-by-field translation: entity ids,
names, and tag URNs stay exactly as Qloo returned them, derived values stay
flagged as the service's own inference.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.models import CallRecord


class EntityRefOut(BaseModel):
    """One resolved entity: id, type URN, display name, city when known."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    name: str
    city: str | None = None


class SeedCandidateOut(BaseModel):
    """One ranked candidate the seed builder renders as a confirm chip."""

    model_config = ConfigDict(extra="forbid")

    entity: EntityRefOut
    confidence: float
    ambiguous: bool
    in_city: bool
    matched_query: str


class SeedQueryOut(BaseModel):
    """The outcome of one seed query: matches or a miss, with a short note."""

    model_config = ConfigDict(extra="forbid")

    text: str
    matches: list[EntityRefOut] = Field(default_factory=list)
    resolved: bool
    note: str = ""


class SeedResolution(BaseModel):
    """Everything ``ResolveBrandSeed`` returns."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[SeedCandidateOut] = Field(default_factory=list)
    queries: list[SeedQueryOut] = Field(default_factory=list)
    confidence: float
    unresolved: bool
    error_code: ErrorCode
    error_message: str = ""
    evidence: list[CallRecord] = Field(default_factory=list)


class ResolvedChipOut(BaseModel):
    """One chip mapped onto a verified tag URN."""

    model_config = ConfigDict(extra="forbid")

    chip: str
    urn: str
    label: str
    type: str
    confidence: float
    free_text: bool


class UnresolvedChipOut(BaseModel):
    """One chip the service refused to guess on; the UI shows the miss."""

    model_config = ConfigDict(extra="forbid")

    chip: str
    reason: str


class TagResolution(BaseModel):
    """Everything ``ResolveTags`` returns."""

    model_config = ConfigDict(extra="forbid")

    resolved: list[ResolvedChipOut] = Field(default_factory=list)
    unresolved: list[UnresolvedChipOut] = Field(default_factory=list)
    error_code: ErrorCode
    error_message: str = ""
    evidence: list[CallRecord] = Field(default_factory=list)


class TagOut(BaseModel):
    """One tag row: the URN, its label, namespace, and shared weight."""

    model_config = ConfigDict(extra="forbid")

    urn: str
    label: str
    type: str
    weight: float | None = None


class DemographicsBucketOut(BaseModel):
    """One age bucket with its delta versus the population baseline."""

    model_config = ConfigDict(extra="forbid")

    label: str
    delta: float


class DemographicsProfileOut(BaseModel):
    """One entity's demographic alignment inputs (PLAN.md section 11)."""

    model_config = ConfigDict(extra="forbid")

    age_buckets: list[DemographicsBucketOut] = Field(default_factory=list)
    male_delta: float = 0.0
    female_delta: float = 0.0


class ExplainabilityOut(BaseModel):
    """One seed input's contribution to a door, straight from Qloo."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    score: float
    label: str = ""


class SubScoreOut(BaseModel):
    """One 0-1 term of the door composite, with its inputs written beside it."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    raw_value: float
    inputs: list[str] = Field(default_factory=list)


class DoorOut(BaseModel):
    """One ranked door: the venue row plus everything the card cites."""

    model_config = ConfigDict(extra="forbid")

    entity: EntityRefOut
    rank: int
    affinity: SubScoreOut | None = None
    demographic_alignment: SubScoreOut | None = None
    distance_meters: float | None = None
    outside_city: bool = False
    shared_tags: list[TagOut] = Field(default_factory=list)
    explainability: list[ExplainabilityOut] = Field(default_factory=list)
    demographics: DemographicsProfileOut | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class SkipReason(StrEnum):
    """Why a candidate sits on the skip list (mirrors ``SkipReasonCode``)."""

    LOW_AFFINITY = "low_affinity"
    COMPETITOR_SATURATION = "competitor_saturation"
    CLOSED = "closed"
    OUTSIDE_CITY = "outside_city"
    UNRESOLVED = "unresolved"


class SkipItemOut(BaseModel):
    """One door on the skip list, with its reason and the compared scores."""

    model_config = ConfigDict(extra="forbid")

    entity: EntityRefOut
    affinity: SubScoreOut | None = None
    reason: SkipReason
    reason_detail: str = ""


class ScoutResult(BaseModel):
    """Everything ``ScoutDoors`` returns."""

    model_config = ConfigDict(extra="forbid")

    doors: list[DoorOut] = Field(default_factory=list)
    skip_list: list[SkipItemOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: ErrorCode
    error_message: str = ""
    evidence: list[CallRecord] = Field(default_factory=list)
