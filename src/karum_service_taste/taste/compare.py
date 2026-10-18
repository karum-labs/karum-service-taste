"""Audience compare (PLAN.md section 12): the conquest-overlap payload.

``CompareAudiences`` calls ``GET /v2/analysis/compare`` for one door against
the emerging brand — or the incumbent the menu audit found — and reads the
documented envelope: ``results.tags`` is the shared-tag overlap, ``results.a``
and ``results.b`` are the per-side tag lists, and ``results.matchEntities`` is
whatever matched outright. The recorded pairs are cross-type (a door against
a brand), so both the overlap and ``matchEntities`` came back empty; the
result degrades cleanly instead of rendering an empty chart (DI-22).

The campaign never dies here (PLAN.md §12): when the call cannot be made or
the pair shares nothing, the result is ``available=False`` with a
deterministic reason, and the door card simply carries no conquest chart.
"""

from __future__ import annotations

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooError
from karum_service_taste.qloo.models import CallRecord
from karum_service_taste.taste.schemas import CompareResult, EntityRefOut, TagOut
from karum_service_taste.taste.scoring import dedupe_warnings, format_warning

#: The recorded compare probes ran at take=50.
COMPARE_TAKE = 50


async def compare_audiences(
    client: QlooClient,
    venue_id: str,
    counterpart_id: str,
    *,
    entity_type: str = "urn:entity:brand",
    take: int = COMPARE_TAKE,
) -> CompareResult:
    """One door against the emerging brand or the incumbent it would displace.

    The venue rides side ``a`` and the counterpart side ``b``, the recorded
    spelling of both lock-pass pairs.
    """
    try:
        response = await client.compare(
            venue_id, counterpart_id, entity_type=entity_type, take=take
        )
    except QlooError as exc:
        reason = f"compare unavailable ({type(exc).__name__}); the conquest chart stays hidden"
        return CompareResult(
            available=False,
            unavailable_reason=reason,
            warnings=[reason],
            error_code=exc.error_code,
            error_message=reason,
        )

    evidence: list[CallRecord] = [response.call] if response.call is not None else []
    warnings = [format_warning(warning) for warning in response.warnings]
    overlap = [
        TagOut(urn=row.tag_id, label=row.name, type=row.subtype or row.type or "", weight=None)
        for row in response.rows
    ]
    matches = [
        EntityRefOut(id=row.entity_id, type=row.type or "", name=row.name)
        for row in response.match_entities
    ]
    if not overlap and not matches:
        reason = "the pair shares no tags and no matching entities; the conquest chart stays hidden"
        return CompareResult(
            available=False,
            unavailable_reason=reason,
            warnings=dedupe_warnings([*warnings, reason]),
            error_code=ErrorCode.UNSPECIFIED,
            error_message=reason,
            evidence=evidence,
        )
    return CompareResult(
        overlap_tags=overlap,
        match_entities=matches,
        match_entities_present=bool(matches),
        available=True,
        warnings=dedupe_warnings(warnings),
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
    )
