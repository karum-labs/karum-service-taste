"""Door scouting (PLAN.md section 10): the ranked board behind the pitch.

``ScoutDoors`` fans out the verified insights calls for a confirmed seed: one
place board per category tag (the collab shape the lock pass recorded), WKT
location with an explicit metre radius, and ``feature.explainability=true``.
Rows merge across the category calls, ranks freeze in encounter order, and the
top doors get a demographics batch in one call — the batch the demographics
endpoint honours, one profile row per signal input. Independent calls run in
parallel under a fan-out cap; every call lands in the evidence list with an
``ev-NNNN`` id that the doors cite.

Recordings replay exactly: a request the pack never recorded raises
``QlooFixtureMissError`` from the client instead of being synthesised.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.models import (
    CallRecord,
    DemographicsRow,
    PlaceRow,
    PlacesResponse,
    QlooWarning,
)
from karum_service_taste.taste.derived import IN_CITY_RADIUS_M, haversine_meters
from karum_service_taste.taste.schemas import (
    DemographicsBucketOut,
    DemographicsProfileOut,
    DoorOut,
    EntityRefOut,
    ExplainabilityOut,
    ScoutResult,
    TagOut,
)

#: Every door board in the lock pass was recorded at take=25.
_DOOR_TAKE = 25

#: One demographics batch carries at most the recorded signal breadth (8 ids).
DETAIL_DOOR_LIMIT = 8

#: Outbound calls that may be in flight at once.
FANOUT_LIMIT = 4


async def scout_doors(
    client: QlooClient,
    seed: Sequence[EntityRefOut],
    *,
    location: tuple[float, float],
    radius_meters: int,
    category_tags: Sequence[str] = (),
    interest_tags: Sequence[str] = (),
    take: int = _DOOR_TAKE,
    detail_limit: int = DETAIL_DOOR_LIMIT,
    fanout_limit: int = FANOUT_LIMIT,
) -> ScoutResult:
    """Rank the door board for a confirmed seed.

    ``location`` is a ``(lat, lon)`` pair. Each category tag gets its own
    place call — the recorded collab shape — so a category that matches
    nothing never masks the others. An all-empty board comes back as
    ``EMPTY`` naming the category, never as invented doors.
    """
    if not seed:
        return ScoutResult(error_code=ErrorCode.VALIDATION, error_message="seed is empty")
    if radius_meters <= 0:
        return ScoutResult(
            error_code=ErrorCode.VALIDATION,
            error_message=(
                "radius_meters must be positive: a point without a radius returns zero rows"
            ),
        )

    entities = [entry.id for entry in seed]
    labels = {entry.id: entry.name for entry in seed}
    categories: list[str | None] = list(category_tags) or [None]
    semaphore = asyncio.Semaphore(max(1, fanout_limit))

    async def place_board(tag: str | None) -> PlacesResponse:
        async with semaphore:
            return await client.insights_places(
                entities,
                location=location,
                radius_m=radius_meters,
                category_tags=[tag] if tag is not None else None,
                interest_tags=list(interest_tags) or None,
                take=take,
            )

    responses = await asyncio.gather(*(place_board(tag) for tag in categories))

    evidence: list[CallRecord] = []
    warnings: list[str] = []
    doors: list[DoorOut] = []
    seen: set[str] = set()
    for tag, response in zip(categories, responses, strict=True):
        call_id = ""
        if response.call is not None:
            evidence.append(response.call)
            call_id = _evidence_id(len(evidence))
        warnings.extend(_format_warning(warning) for warning in response.warnings)
        if tag is not None and not response.rows:
            warnings.append(f"category {tag} matched no doors")
        for row in response.rows:
            if row.entity_id in seen:
                continue
            seen.add(row.entity_id)
            doors.append(
                _door_from_row(
                    row,
                    rank=len(doors) + 1,
                    point=location,
                    labels=labels,
                    call_id=call_id,
                )
            )

    if not doors:
        matched = ", ".join(tag for tag in categories if tag is not None)
        return ScoutResult(
            warnings=warnings,
            error_code=ErrorCode.EMPTY,
            error_message=f"no doors matched {matched or 'the seed'}",
            evidence=evidence,
        )

    detail_ids = [door.entity.id for door in doors[: min(detail_limit, DETAIL_DOOR_LIMIT)]]
    if detail_ids:
        async with semaphore:
            profiles = await client.insights_demographics(detail_ids)
        detail_call_id = ""
        if profiles.call is not None:
            evidence.append(profiles.call)
            detail_call_id = _evidence_id(len(evidence))
        warnings.extend(_format_warning(warning) for warning in profiles.warnings)
        by_id = {row.entity_id: row for row in profiles.rows}
        for door in doors[: len(detail_ids)]:
            row = by_id.get(door.entity.id)
            if row is not None:
                door.demographics = _profile_from_row(row)
                if detail_call_id:
                    door.evidence_ids.append(detail_call_id)

    return ScoutResult(
        doors=doors,
        warnings=warnings,
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
    )


def _door_from_row(
    row: PlaceRow,
    *,
    rank: int,
    point: tuple[float, float],
    labels: dict[str, str],
    call_id: str,
) -> DoorOut:
    """Fold one Qloo place row into the door the card cites."""
    row_point = (row.location.lat, row.location.lon) if row.location is not None else None
    distance = haversine_meters(row_point, point) if row_point is not None else None
    contributions: list[ExplainabilityOut] = []
    if row.query.explainability:
        for contribution in row.query.explainability.get("signal.interests.entities", []):
            contributions.append(
                ExplainabilityOut(
                    entity_id=contribution.entity_id,
                    score=contribution.score,
                    label=labels.get(contribution.entity_id, ""),
                )
            )
    geocode = row.properties.geocode
    return DoorOut(
        entity=EntityRefOut(
            id=row.entity_id,
            type=row.type or "urn:entity:place",
            name=row.name,
            city=geocode.city if geocode is not None else None,
        ),
        rank=rank,
        affinity_raw=row.query.affinity,
        distance_meters=distance,
        outside_city=distance is not None and distance > IN_CITY_RADIUS_M,
        shared_tags=[
            TagOut(urn=tag.id, label=tag.name, type=tag.type or "", weight=tag.weight)
            for tag in row.tags
        ],
        explainability=contributions,
        evidence_ids=[call_id] if call_id else [],
    )


def _profile_from_row(row: DemographicsRow) -> DemographicsProfileOut:
    """Map one demographics row onto the profile the card renders."""
    return DemographicsProfileOut(
        age_buckets=[
            DemographicsBucketOut(label=label, delta=delta) for label, delta in row.age.items()
        ],
        male_delta=row.gender.get("male", 0.0),
        female_delta=row.gender.get("female", 0.0),
    )


def _format_warning(warning: QlooWarning) -> str:
    """One upstream warning as the operator-readable line it becomes."""
    if warning.missing_entities:
        return f"{warning.type}: {', '.join(warning.missing_entities)}"
    return warning.type


def _evidence_id(position: int) -> str:
    """The proto's citation form: ``ev-0001`` is a run's first call."""
    return f"ev-{position:04d}"
