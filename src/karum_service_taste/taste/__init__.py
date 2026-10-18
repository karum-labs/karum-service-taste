"""Taste resolution layer: seeds, tags, doors, the map layers, and compare.

Implements PLAN.md sections 8-14. Each resolver returns a typed result model
that mirrors the frozen ``karum.taste.v1`` protos, so the gRPC servicer is a
field-by-field translation.
"""

from karum_service_taste.taste.compare import COMPARE_TAKE, compare_audiences
from karum_service_taste.taste.doors import DETAIL_DOOR_LIMIT, scout_doors
from karum_service_taste.taste.heatmap import (
    ANCHOR_LIMIT,
    CORRIDOR_LIMIT,
    HEATMAP_TAKE,
    AnchorPlace,
    locality_heatmap,
)
from karum_service_taste.taste.schemas import (
    CompareResult,
    DoorOut,
    EntityRefOut,
    GeoPointOut,
    HeatmapCellOut,
    HeatmapResult,
    LocalityPolygonOut,
    ResolvedChipOut,
    ScoutResult,
    SeedCandidateOut,
    SeedQueryOut,
    SeedResolution,
    SkipItemOut,
    SkipReason,
    SubScoreOut,
    TagOut,
    TagResolution,
    UnresolvedChipOut,
)
from karum_service_taste.taste.scoring import FANOUT_LIMIT, resolve_skip_names
from karum_service_taste.taste.seed import DEFAULT_CACHE_TTL_SECONDS, resolve_brand_seed
from karum_service_taste.taste.tags import ALLOWED_NAMESPACES, resolve_tags

__all__ = [
    "ALLOWED_NAMESPACES",
    "ANCHOR_LIMIT",
    "AnchorPlace",
    "COMPARE_TAKE",
    "CORRIDOR_LIMIT",
    "CompareResult",
    "DEFAULT_CACHE_TTL_SECONDS",
    "DETAIL_DOOR_LIMIT",
    "DoorOut",
    "EntityRefOut",
    "FANOUT_LIMIT",
    "GeoPointOut",
    "HEATMAP_TAKE",
    "HeatmapCellOut",
    "HeatmapResult",
    "LocalityPolygonOut",
    "ResolvedChipOut",
    "ScoutResult",
    "SeedCandidateOut",
    "SeedQueryOut",
    "SeedResolution",
    "SkipItemOut",
    "SkipReason",
    "SubScoreOut",
    "TagOut",
    "TagResolution",
    "UnresolvedChipOut",
    "compare_audiences",
    "locality_heatmap",
    "resolve_brand_seed",
    "resolve_skip_names",
    "resolve_tags",
    "scout_doors",
]
