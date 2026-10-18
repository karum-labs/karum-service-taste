"""Taste resolution layer: seeds, tags, and the scores built on them.

Implements PLAN.md sections 8-14. Each resolver returns a typed result model
that mirrors the frozen ``karum.taste.v1`` protos, so the gRPC servicer is a
field-by-field translation.
"""

from karum_service_taste.taste.schemas import (
    EntityRefOut,
    ResolvedChipOut,
    SeedCandidateOut,
    SeedQueryOut,
    SeedResolution,
    TagResolution,
    UnresolvedChipOut,
)
from karum_service_taste.taste.seed import DEFAULT_CACHE_TTL_SECONDS, resolve_brand_seed
from karum_service_taste.taste.tags import ALLOWED_NAMESPACES, resolve_tags

__all__ = [
    "ALLOWED_NAMESPACES",
    "DEFAULT_CACHE_TTL_SECONDS",
    "EntityRefOut",
    "ResolvedChipOut",
    "SeedCandidateOut",
    "SeedQueryOut",
    "SeedResolution",
    "TagResolution",
    "UnresolvedChipOut",
    "resolve_brand_seed",
    "resolve_tags",
]
