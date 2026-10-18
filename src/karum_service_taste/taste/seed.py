"""Brand seed resolution (PLAN.md §8).

``ResolveBrandSeed`` searches the brand query and each fallback vibe query
through ``GET /search`` and returns ranked candidates with a derived
confidence. The brand query searches brand-typed first and the vibe queries
place-typed first — the spellings the lock pass recorded — and each query
walks the remaining entity types when a stage returns nothing. A query that
hits nothing is a miss, never a guess; a seed with no hits at all is
``unresolved``. Hits and negative lookups cache under a short TTL.
"""

from __future__ import annotations

from collections.abc import Sequence

from karum_service_taste.core.cache import TtlCache
from karum_service_taste.qloo.canonical import format_params
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.models import CallRecord, SearchEntity
from karum_service_taste.taste.derived import (
    LOW_CONFIDENCE,
    derived_confidence,
    in_city,
    normalize_text,
)
from karum_service_taste.taste.schemas import (
    EntityRefOut,
    SeedCandidateOut,
    SeedQueryOut,
    SeedResolution,
)

# The spelling every seed-search recording used: take 5, page 1, one entity
# type per call (RECORDING.md, 18 Oct lock pass).
_SEARCH_TAKE = 5
_SEARCH_PAGE = 1

_TYPE_BRAND = "urn:entity:brand"
_TYPE_PLACE = "urn:entity:place"
_TYPE_ARTIST = "urn:entity:artist"

_TYPE_LABELS = {
    _TYPE_BRAND: "brand",
    _TYPE_PLACE: "place",
    _TYPE_ARTIST: "artist",
}

# Escalation order per query role: a brand query is a brand name first, a
# vibe query is a venue first. Each query walks every type at most once.
_ESCALATION = {
    "brand": (_TYPE_BRAND, _TYPE_PLACE, _TYPE_ARTIST),
    "vibe": (_TYPE_PLACE, _TYPE_BRAND, _TYPE_ARTIST),
}

# Lookups — hits and negative lookups — cache for this long (PLAN.md §8).
DEFAULT_CACHE_TTL_SECONDS = 300.0


async def resolve_brand_seed(
    client: QlooClient,
    brand_query: str,
    *,
    fallback_queries: Sequence[str] = (),
    location: tuple[float, float] | None = None,
    city: str | None = None,
    take: int = _SEARCH_TAKE,
    cache: TtlCache[list[SearchEntity]] | None = None,
) -> SeedResolution:
    """Resolve the brand query and fallback vibe queries into candidates.

    ``location`` is the preset ``(lat, lon)`` point used for the in-city
    check; ``city`` is the city label used in the honesty notes.
    """
    brand_text = brand_query.strip() if brand_query else ""
    if not brand_text:
        return SeedResolution(
            confidence=0.0,
            unresolved=True,
            error_code=ErrorCode.VALIDATION,
            error_message="brand query is empty",
        )

    queries: list[tuple[str, str]] = [("brand", brand_text)]
    queries.extend(("vibe", text.strip()) for text in fallback_queries if text and text.strip())

    evidence: list[CallRecord] = []
    candidates: list[SeedCandidateOut] = []
    outcomes: list[SeedQueryOut] = []

    for role, text in queries:
        rows, calls, stages = await _search_query(client, text, role, take=take, cache=cache)
        evidence.extend(calls)
        if not rows:
            types_tried = " or ".join(
                _TYPE_LABELS[entity_type] for entity_type in _ESCALATION[role]
            )
            outcomes.append(
                SeedQueryOut(
                    text=text,
                    resolved=False,
                    note=f"no match for {text!r} as {types_tried}",
                )
            )
            continue
        query_candidates = _rank_candidates(text, rows, location)
        candidates.extend(query_candidates)
        notes: list[str] = []
        if stages > 1:
            kind = _TYPE_LABELS.get(query_candidates[0].entity.type, "match")
            notes.append(f"resolved as a {kind} after an empty earlier lookup")
        if query_candidates[0].confidence < LOW_CONFIDENCE:
            notes.append("closest rows are weak matches - confirm the seed")
        elif city and not any(candidate.in_city for candidate in query_candidates):
            notes.append(f"no row verified inside {city}")
        outcomes.append(
            SeedQueryOut(
                text=text,
                matches=[candidate.entity for candidate in query_candidates],
                resolved=True,
                note="; ".join(notes),
            )
        )

    if not candidates:
        missed = ", ".join(repr(outcome.text) for outcome in outcomes)
        return SeedResolution(
            queries=outcomes,
            confidence=0.0,
            unresolved=True,
            error_code=ErrorCode.UNRESOLVED,
            error_message=f"no seed query resolved: {missed}",
            evidence=evidence,
        )

    # Collapse duplicate venues to one entity (by entity id).
    candidates = _dedupe_entities(candidates)

    # At this point we have at least one candidate. Compute confidence.
    resolved_outcomes = [outcome for outcome in outcomes if outcome.resolved]
    if not resolved_outcomes:
        # All queries missed; seed is unresolved.
        return SeedResolution(
            queries=outcomes,
            confidence=0.0,
            unresolved=True,
            error_code=ErrorCode.UNRESOLVED,
            error_message="no seed query resolved",
            evidence=evidence,
        )

    tops = [
        next(
            candidate.confidence
            for candidate in candidates
            if candidate.matched_query == outcome.text
        )
        for outcome in resolved_outcomes
    ]
    confidence = round(sum(tops) / len(tops) * len(resolved_outcomes) / len(outcomes), 4)
    return SeedResolution(
        candidates=candidates,
        queries=outcomes,
        confidence=confidence,
        unresolved=False,
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
    )


async def _search_query(
    client: QlooClient,
    text: str,
    role: str,
    *,
    take: int,
    cache: TtlCache[list[SearchEntity]] | None,
) -> tuple[list[SearchEntity], list[CallRecord], int]:
    """Walk the role's type escalation; return rows, call records, stages walked."""
    evidence: list[CallRecord] = []
    stages = 0
    for entity_type in _ESCALATION[role]:
        stages += 1
        params = [
            ("query", text),
            ("types", entity_type),
            ("take", str(take)),
            ("page", str(_SEARCH_PAGE)),
        ]
        key = format_params(params)
        if cache is not None:
            cached = cache.get(key)
            if cached is not None:
                if cached:
                    return cached, evidence, stages
                continue
        response = await client.search(text, types=[entity_type], take=take, page=_SEARCH_PAGE)
        if response.call is not None:
            evidence.append(response.call)
        rows = list(response.rows)
        if cache is not None:
            cache.set(key, rows)
        if rows:
            return rows, evidence, stages
    return [], evidence, stages


def _rank_candidates(
    text: str,
    rows: Sequence[SearchEntity],
    location: tuple[float, float] | None,
) -> list[SeedCandidateOut]:
    """Turn one query's rows into candidates with derived flags."""
    prepared: list[tuple[SearchEntity, float, bool, str | None]] = []
    for index, row in enumerate(rows):
        point = (row.location.lat, row.location.lon) if row.location is not None else None
        city_label = row.geocode.city if row.geocode is not None else None
        prepared.append(
            (
                row,
                derived_confidence(text, row.name, index + 1),
                in_city(point, location),
                city_label,
            )
        )
    collisions = _colliding_names(prepared)
    return [
        SeedCandidateOut(
            entity=EntityRefOut(
                id=row.entity_id,
                type=row.types[0] if row.types else "",
                name=row.name,
                city=city_label,
            ),
            confidence=confidence,
            ambiguous=confidence < LOW_CONFIDENCE or normalize_text(row.name) in collisions,
            in_city=within,
            matched_query=text,
        )
        for row, confidence, within, city_label in prepared
    ]


def _colliding_names(
    prepared: Sequence[tuple[SearchEntity, float, bool, str | None]],
) -> set[str]:
    """Names whose rows disagree on city membership — a real collision."""
    memberships: dict[str, set[bool]] = {}
    for row, _confidence, within, _city_label in prepared:
        memberships.setdefault(normalize_text(row.name), set()).add(within)
    return {name for name, flags in memberships.items() if len(flags) > 1}


def _dedupe_entities(
    candidates: Sequence[SeedCandidateOut],
) -> list[SeedCandidateOut]:
    """Collapse duplicate venues to one entity (by entity id), keeping the first."""

    seen: set[str] = set()
    result: list[SeedCandidateOut] = []
    for candidate in candidates:
        eid = candidate.entity.id
        if eid in seen:
            continue
        seen.add(eid)
        result.append(candidate)
    return result
