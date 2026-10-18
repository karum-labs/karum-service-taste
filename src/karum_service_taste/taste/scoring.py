"""Scoring (PLAN.md section 11): A_taste, D_demo, and the relative skip list.

The service returns sub-scores, never the composite: the gateway computes
``S_door = 0.50 * A_taste + 0.30 * O_shelf + 0.20 * D_demo`` from them and
displays ``100 * S_door`` (TECH.md). Two rules are pinned here:

- ``A_taste`` is the affinity's percentile inside the returned set, because
  raw affinity bands move with the seed and the city; the raw affinity always
  rides in ``raw_value`` as the Qloo fact.
- The skip list is relative: candidates are batch-scored in one
  ``filter.results.entities`` call and everything strictly below the ranked
  pool's floor (its minimum; never an absolute threshold) lands on the skip
  list with a machine-readable reason. A candidate exactly at the floor stays
  on the board.

Free-entry runs name candidates instead of listing ids; each name resolves
through ``/search`` and a name that never resolves stays visible as an
``unresolved`` skip item rather than being dropped or scored.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.models import CallRecord, QlooWarning, SearchEntity, SearchResponse
from karum_service_taste.taste.derived import LOW_CONFIDENCE, derived_confidence, in_city
from karum_service_taste.taste.schemas import (
    EntityRefOut,
    SkipItemOut,
    SkipReason,
    SubScoreOut,
)

#: The ranked pool probe records take=50; its minimum is the relative floor.
POOL_TAKE = 50

#: The batch scoring call mirrors the recorded probe (take=25).
SKIP_BATCH_TAKE = 25

#: Outbound calls that may be in flight at once.
FANOUT_LIMIT = 4


def percentile_of(value: float, peers: Sequence[float]) -> float:
    """The nearest-rank percentile: the share of peers scored strictly below.

    The top of a set is 1.0 and the bottom 0.0; equal values share their
    percentile, and a singleton (or empty) set is 1.0.
    """
    if len(peers) <= 1:
        return 1.0
    below = sum(1 for peer in peers if peer < value)
    return below / (len(peers) - 1)


def affinity_subscore(
    value: float, peers: Sequence[float], *, inputs: Sequence[str]
) -> SubScoreOut:
    """The cultural-affinity bundle: the derived percentile beside the raw value."""
    return SubScoreOut(
        name="cultural_affinity",
        value=percentile_of(value, peers),
        raw_value=value,
        inputs=list(inputs),
    )


def demographic_subscore(
    door_deltas: Mapping[str, float], target_deltas: Mapping[str, float]
) -> SubScoreOut | None:
    """``D_demo``: age-bucket alignment against the brand's target cohort.

    Cosine similarity over the union of buckets (a missing bucket counts as
    zero), mapped onto 0-1 as ``(cos + 1) / 2``; ``raw_value`` keeps the
    cosine itself. ``None`` when either side is empty or flat — an unverified
    term the composite renormalizes over, never a fabricated zero.
    """
    keys = sorted(
        key
        for key in set(door_deltas) | set(target_deltas)
        if door_deltas.get(key, 0.0) or target_deltas.get(key, 0.0)
    )
    if not keys:
        return None
    left = [door_deltas.get(key, 0.0) for key in keys]
    right = [target_deltas.get(key, 0.0) for key in keys]
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    cosine = sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
    return SubScoreOut(
        name="demographic_alignment",
        value=(cosine + 1.0) / 2.0,
        raw_value=cosine,
        inputs=[f"age_buckets={len(keys)}", "mapping=cosine01"],
    )


def format_warning(warning: QlooWarning) -> str:
    """One upstream warning as the operator-readable line it becomes."""
    if warning.missing_entities:
        return f"{warning.type}: {', '.join(warning.missing_entities)}"
    return warning.type


def dedupe_warnings(warnings: Sequence[str]) -> list[str]:
    """Warnings as distinct lines, in the order the run first met them."""
    return list(dict.fromkeys(warnings))


def skip_item(
    entity: EntityRefOut, raw: float, floor: float, peers: Sequence[float]
) -> SkipItemOut:
    """One candidate below the relative floor, its reasons attached."""
    return SkipItemOut(
        entity=entity,
        affinity=affinity_subscore(raw, peers, inputs=[f"pool={len(peers)}", f"floor={floor:.4f}"]),
        reason=SkipReason.LOW_AFFINITY,
        reason_detail=f"{raw:.4f} below the returned floor {floor:.4f}",
    )


@dataclass(frozen=True)
class NameResolution:
    """The outcome of resolving free-entry candidate names via ``/search``."""

    ids: list[str] = field(default_factory=list)
    unresolved: list[SkipItemOut] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[CallRecord] = field(default_factory=list)


async def resolve_skip_names(
    client: QlooClient,
    names: Sequence[str],
    *,
    location: tuple[float, float] | None = None,
    fanout_limit: int = FANOUT_LIMIT,
) -> NameResolution:
    """Resolve candidate names to place ids, keeping the misses visible.

    Each name gets one recorded ``/search`` spelling (place-typed, take 5,
    page 1). The pick prefers a row inside the preset city, then the strongest
    derived name match; a name with no confident place row becomes an
    ``unresolved`` skip item — recorded as a miss, never scored.
    """
    semaphore = asyncio.Semaphore(max(1, fanout_limit))

    async def lookup(name: str) -> SearchResponse:
        async with semaphore:
            return await client.search(name, types=["urn:entity:place"], take=5, page=1)

    responses = await asyncio.gather(*(lookup(name) for name in names))

    ids: list[str] = []
    unresolved: list[SkipItemOut] = []
    warnings: list[str] = []
    evidence: list[CallRecord] = []
    for name, response in zip(names, responses, strict=True):
        if response.call is not None:
            evidence.append(response.call)
        warnings.extend(format_warning(warning) for warning in response.warnings)
        pick = _pick_place(name, response.rows, location)
        if pick is None:
            unresolved.append(
                SkipItemOut(
                    entity=EntityRefOut(id="", type="urn:entity:place", name=name),
                    reason=SkipReason.UNRESOLVED,
                    reason_detail="never resolved in Qloo: no confident place row",
                )
            )
            continue
        if pick.entity_id not in ids:
            ids.append(pick.entity_id)
    return NameResolution(ids=ids, unresolved=unresolved, warnings=warnings, evidence=evidence)


def _pick_place(
    query: str, rows: Sequence[SearchEntity], location: tuple[float, float] | None
) -> SearchEntity | None:
    """The best place row for a name: in-city first, then name match, then rank."""
    best: tuple[tuple[bool, float, int], SearchEntity] | None = None
    for rank, row in enumerate(rows, start=1):
        confidence = derived_confidence(query, row.name, rank)
        if confidence < LOW_CONFIDENCE:
            continue
        point = (row.location.lat, row.location.lon) if row.location is not None else None
        # ``in_city`` is False for a row without a point, so a located row
        # inside the preset city always outranks a row without one.
        inside = in_city(point, location) if location is not None else True
        key = (not inside, -confidence, rank)
        if best is None or key < best[0]:
            best = (key, row)
    return best[1] if best is not None else None
