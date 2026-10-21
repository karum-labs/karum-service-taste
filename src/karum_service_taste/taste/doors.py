"""Door scouting (PLAN.md sections 10-11): the ranked board and the skip list.

``ScoutDoors`` fans out the verified insights calls for a confirmed seed: one
place board per category tag (the collab shape the lock pass recorded), WKT
location with an explicit metre radius, and ``feature.explainability=true``.
Rows merge across the category calls, ranks freeze in encounter order, and the
returned board is the shortlist every door percentile is measured in.

Scoring rides the same run (PLAN.md section 11):

- every door carries its ``A_taste`` bundle — the affinity's percentile inside
  the returned board, with the raw affinity kept as the Qloo fact;
- the top doors get a demographics batch, and when the seed's own profile is
  available their ``D_demo`` alignment against the brand's age buckets;
- the skip list is relative: a ranked pool call fixes the floor (its
  minimum), the candidates are batch-scored in one ``filter.results.entities``
  call, and everything strictly below the floor lands on the skip list with a
  machine-readable reason. A candidate exactly at the floor stays on the
  board; an absolute threshold never fires.

The enrichment calls degrade visibly: a demographics batch or the pool probe
that cannot be made leaves its derived term unverified and names the
degradation in the warnings instead of fabricating a value. Profile calls
drop entities the board flagged as unknown upstream (the recorded Colaba seed
excludes its one ``not_found`` id). The door board itself never degrades — a
request the pack cannot replay raises ``QlooFixtureMissError`` from the
client.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooError
from karum_service_taste.qloo.models import (
    CallRecord,
    DemographicsResponse,
    DemographicsRow,
    PlaceRow,
    PlacesResponse,
)
from karum_service_taste.taste.derived import IN_CITY_RADIUS_M, haversine_meters
from karum_service_taste.taste.schemas import (
    DemographicsBucketOut,
    DemographicsProfileOut,
    DoorOut,
    EntityRefOut,
    ExplainabilityOut,
    PlaceFactsOut,
    ScoutResult,
    SkipItemOut,
    TagOut,
)
from karum_service_taste.taste.scoring import (
    FANOUT_LIMIT,
    POOL_TAKE,
    SKIP_BATCH_TAKE,
    affinity_subscore,
    dedupe_warnings,
    demographic_subscore,
    format_warning,
    resolve_skip_names,
    skip_item,
)

#: Every door board in the lock pass was recorded at take=25.
_DOOR_TAKE = 25

#: One demographics batch carries at most the recorded signal breadth (8 ids).
DETAIL_DOOR_LIMIT = 8


async def scout_doors(
    client: QlooClient,
    seed: Sequence[EntityRefOut],
    *,
    location: tuple[float, float],
    radius_meters: int,
    category_tags: Sequence[str] = (),
    interest_tags: Sequence[str] = (),
    skip_candidate_ids: Sequence[str] = (),
    skip_candidate_names: Sequence[str] = (),
    take: int = _DOOR_TAKE,
    pool_take: int = POOL_TAKE,
    detail_limit: int = DETAIL_DOOR_LIMIT,
    fanout_limit: int = FANOUT_LIMIT,
) -> ScoutResult:
    """Rank the door board for a confirmed seed and score its skip list.

    ``location`` is a ``(lat, lon)`` pair. Each category tag gets its own place
    call — the recorded collab shape — so a category that matches nothing
    never masks the others. Skip candidates arrive as verified ids (presets)
    or venue names (free entry). An all-empty board comes back as ``EMPTY``
    naming the category, never as invented doors.
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
    raw_by_id: dict[str, float] = {}
    seen: set[str] = set()
    missing: set[str] = set()
    seed_ids = {e.id for e in seed if e.id}
    for tag, response in zip(categories, responses, strict=True):
        call_id = ""
        if response.call is not None:
            evidence.append(response.call)
            call_id = _evidence_id(len(evidence))
        for warning in response.warnings:
            warnings.append(format_warning(warning))
            missing.update(warning.missing_entities)
        if tag is not None and not response.rows:
            warnings.append(f"category {tag} matched no doors")
        for row in response.rows:
            if row.entity_id in seen:
                continue
            if row.entity_id in seed_ids:
                continue  # drop results that are seed entities
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
            if row.query.affinity is not None:
                raw_by_id[row.entity_id] = row.query.affinity

    if not doors:
        matched = ", ".join(tag for tag in categories if tag is not None)
        return ScoutResult(
            warnings=dedupe_warnings(warnings),
            error_code=ErrorCode.EMPTY,
            error_message=f"no doors matched {matched or 'the seed'}",
            evidence=evidence,
        )

    peers = [raw_by_id[door.entity.id] for door in doors if door.entity.id in raw_by_id]
    for door in doors:
        raw = raw_by_id.get(door.entity.id)
        if raw is not None:
            door.affinity = affinity_subscore(
                raw, peers, inputs=[f"rank={door.rank}", f"shortlist={len(peers)}"]
            )

    # Profile calls drop entities the board flagged as unknown upstream (the
    # recorded Colaba seed excludes its one ``not_found`` id); ranking and
    # scoring calls keep the seed exactly as the scenario defined it.
    demo_entities = [entity_id for entity_id in entities if entity_id not in missing]

    names_resolution = None
    if skip_candidate_names:
        names_resolution = await resolve_skip_names(
            client,
            list(skip_candidate_names),
            location=location,
            fanout_limit=fanout_limit,
        )
        evidence.extend(names_resolution.evidence)
        warnings.extend(names_resolution.warnings)

    candidates: list[str] = list(skip_candidate_ids)
    if names_resolution is not None:
        candidates.extend(
            entity_id for entity_id in names_resolution.ids if entity_id not in candidates
        )

    detail_ids = [door.entity.id for door in doors[: min(detail_limit, DETAIL_DOOR_LIMIT)]]

    async def run_seed_demographics() -> tuple[DemographicsResponse | None, str | None]:
        try:
            async with semaphore:
                response = await client.insights_demographics(demo_entities)
            return response, None
        except QlooError as exc:
            return None, (
                f"seed demographics unavailable ({type(exc).__name__}); "
                "demographic alignment left unverified"
            )

    async def run_pool() -> tuple[PlacesResponse | None, str | None]:
        try:
            async with semaphore:
                response = await client.insights_places(
                    entities,
                    location=location,
                    radius_m=radius_meters,
                    take=pool_take,
                    explainability=False,
                )
            return response, None
        except QlooError as exc:
            return None, (
                f"ranked pool probe unavailable ({type(exc).__name__}); "
                "floor falls back to the door board"
            )

    async def run_door_demographics() -> tuple[DemographicsResponse | None, str | None]:
        try:
            async with semaphore:
                response = await client.insights_demographics(detail_ids)
            return response, None
        except QlooError as exc:
            return None, (
                f"door demographics unavailable ({type(exc).__name__}); alignment stays unverified"
            )

    async def run_skip_batch() -> tuple[PlacesResponse | None, str | None]:
        try:
            async with semaphore:
                response = await client.insights_places(
                    entities,
                    location=location,
                    radius_m=radius_meters,
                    results_entities=candidates,
                    take=SKIP_BATCH_TAKE,
                    explainability=False,
                )
            return response, None
        except QlooError as exc:
            return None, (
                f"skip batch unavailable ({type(exc).__name__}); candidates were not scored"
            )

    jobs: dict[str, Coroutine[Any, Any, Any]] = {}
    if demo_entities:
        jobs["seed_demographics"] = run_seed_demographics()
    else:
        warnings.append("seed demographics skipped: no seed entity resolved upstream")
    if candidates:
        jobs["pool"] = run_pool()
    if detail_ids:
        jobs["door_demographics"] = run_door_demographics()
    if candidates:
        jobs["skip_batch"] = run_skip_batch()
    settled = await asyncio.gather(*jobs.values())
    outcomes = dict(zip(jobs.keys(), settled, strict=True))

    seed_profiles, seed_failure = outcomes.get("seed_demographics", (None, None))
    if seed_failure is not None:
        warnings.append(seed_failure)
    if seed_profiles is not None:
        if seed_profiles.call is not None:
            evidence.append(seed_profiles.call)
        warnings.extend(format_warning(warning) for warning in seed_profiles.warnings)
    target_row = (
        _pick_profile(seed_profiles.rows, entities[0]) if seed_profiles is not None else None
    )

    pool, pool_failure = outcomes.get("pool", (None, None))
    pool_peers: list[float] = []
    if pool_failure is not None:
        warnings.append(pool_failure)
    if pool is not None:
        if pool.call is not None:
            evidence.append(pool.call)
        warnings.extend(format_warning(warning) for warning in pool.warnings)
        pool_peers = [row.query.affinity for row in pool.rows if row.query.affinity is not None]
        if not pool_peers:
            warnings.append(
                "ranked pool returned no affinity rows; floor falls back to the door board"
            )
    board_floor = min(peers) if peers else None
    floor = min(pool_peers) if pool_peers else board_floor

    door_profiles, door_failure = outcomes.get("door_demographics", (None, None))
    if door_failure is not None:
        warnings.append(door_failure)
    if door_profiles is not None:
        call_id = ""
        if door_profiles.call is not None:
            evidence.append(door_profiles.call)
            call_id = _evidence_id(len(evidence))
        warnings.extend(format_warning(warning) for warning in door_profiles.warnings)
        by_id = {row.entity_id: row for row in door_profiles.rows}
        for door in doors[: len(detail_ids)]:
            row = by_id.get(door.entity.id)
            if row is None:
                continue
            door.demographics = _profile_from_row(row)
            if call_id:
                door.evidence_ids.append(call_id)
            if target_row is not None:
                door.demographic_alignment = demographic_subscore(row.age, target_row.age)
                alignment = door.demographic_alignment
                if alignment is not None and alignment.value < 0.5:
                    warnings.append(
                        f"demographic mismatch at {door.entity.name}: "
                        f"D_demo {alignment.value:.2f} runs against the brand cohort"
                    )

    skip_items: list[SkipItemOut] = []
    batch, batch_failure = outcomes.get("skip_batch", (None, None))
    if batch_failure is not None:
        warnings.append(batch_failure)
    if batch is not None:
        if batch.call is not None:
            evidence.append(batch.call)
        warnings.extend(format_warning(warning) for warning in batch.warnings)
        comparison = pool_peers or peers
        if floor is None:
            warnings.append("no affinity floor available; skip candidates were not classified")
        else:
            scored: list[tuple[float, SkipItemOut]] = []
            for row in batch.rows:
                raw = row.query.affinity
                if raw is None:
                    warnings.append(f"candidate {row.name} came back without an affinity")
                    continue
                if raw < floor:
                    scored.append((raw, skip_item(_entity_ref(row), raw, floor, comparison)))
            scored.sort(key=lambda pair: (-pair[0], pair[1].entity.id))
            skip_items = [item for _, item in scored]
    if names_resolution is not None:
        skip_items.extend(names_resolution.unresolved)

    return ScoutResult(
        doors=doors,
        skip_list=skip_items,
        warnings=dedupe_warnings(warnings),
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
        affinity_floor=floor or 0.0,
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
    return DoorOut(
        entity=_entity_ref(row),
        rank=rank,
        distance_meters=distance,
        outside_city=distance is not None and distance > IN_CITY_RADIUS_M,
        shared_tags=[
            TagOut(urn=tag.id, label=tag.name, type=tag.type or "", weight=tag.weight)
            for tag in row.tags
        ],
        explainability=contributions,
        evidence_ids=[call_id] if call_id else [],
    )


def _entity_ref(row: PlaceRow) -> EntityRefOut:
    """The entity reference a door card (or a skip row) shows."""
    geocode = row.properties.geocode
    return EntityRefOut(
        id=row.entity_id,
        type=row.type or "urn:entity:place",
        name=row.name,
        city=geocode.city if geocode is not None else None,
        place=_place_facts(row),
    )


_HOUR_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _hours_text(hours: dict) -> str:
    """Fold Qloo's per-day intervals into one display line."""
    parts: list[str] = []
    for day in _HOUR_DAYS:
        intervals = hours.get(day)
        if not intervals:
            continue
        for interval in intervals:
            if getattr(interval, "closed", False):
                parts.append(f"{day[:3].title()}: closed")
                continue
            opens = getattr(interval, "opens", None)
            closes = getattr(interval, "closes", None)
            if opens and closes:
                parts.append(f"{day[:3].title()} {opens}-{closes}")
            elif opens:
                parts.append(f"{day[:3].title()} from {opens}")
    return "; ".join(parts)


def _place_facts(row: PlaceRow) -> PlaceFactsOut:
    """The recorded property block Qloo returned beside a place row."""
    properties = row.properties
    location = row.location
    return PlaceFactsOut(
        address=properties.address or "",
        website=properties.website or "",
        phone=properties.phone or "",
        hours=_hours_text(properties.hours),
        is_closed=bool(properties.is_closed),
        lat=location.lat if location is not None else None,
        lon=location.lon if location is not None else None,
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


def _pick_profile(rows: Sequence[DemographicsRow], brand_id: str) -> DemographicsRow | None:
    """The target cohort row: the brand anchor's profile, else the first row."""
    for row in rows:
        if row.entity_id == brand_id:
            return row
    return rows[0] if rows else None


def _evidence_id(position: int) -> str:
    """The proto's citation form: ``ev-0001`` is a run's first call."""
    return f"ev-{position:04d}"
