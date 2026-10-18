"""Result schemas for the taste resolution layer.

These mirror the frozen protos in ``karum-infra/proto/karum/taste/v1`` closely
enough that the gRPC servicer is a field-by-field translation: entity ids,
names, and tag URNs stay exactly as Qloo returned them, derived values stay
flagged as the service's own inference.
"""

from __future__ import annotations

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
