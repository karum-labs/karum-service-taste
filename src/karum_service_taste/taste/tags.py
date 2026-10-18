"""Tag resolution (PLAN.md §9).

``ResolveTags`` maps campaign category chips onto verified tag URNs through
``GET /v2/tags``. The four campaign categories are pinned to the probes the
lock pass recorded — including each probe's ``take`` — so fixture replay is
exact. Free text is accepted only on a confident derived hit, because
``/v2/tags`` publishes no score; anything else comes back unresolved. An
allow-list of tag namespaces keeps the pitch to the tags it can explain.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.qloo.models import CallRecord, CatalogTag
from karum_service_taste.taste.derived import (
    LOW_CONFIDENCE,
    derived_confidence,
    normalize_text,
)
from karum_service_taste.taste.schemas import (
    ResolvedChipOut,
    TagResolution,
    UnresolvedChipOut,
)

# Every recorded chip search restricted the namespace server-side
# (QLOO_APIS.md §3.2: `filter.tag.types=urn:tag:genre` on each lock-pass call).
_TAG_NAMESPACE = "urn:tag:genre"

# The allow-list of tag namespaces the pitch knows how to explain (PLAN.md
# §9). The four verified chips all live under it. `/v2/tags/types` — the
# documented source for this list (QLOO_APIS.md §3.2b) — is not recorded yet,
# so the verified namespace stands in until it is.
ALLOWED_NAMESPACES = ("urn:tag:genre",)

# Free-text chips search with this take; preset chips carry their own.
FREE_TEXT_TAKE = 25


@dataclass(frozen=True)
class _ChipSpec:
    """One verified preset chip: the probe that recorded it and its URN."""

    query: str
    take: int
    urn: str


# The four campaign categories, pinned to their 18 Oct probes. `take` is the
# recorded probe's value (bar was probed at 15, the rest at 25) so fixture
# replay is exact; the catalogue is a closed set and unknown text is only
# accepted through a confident live tag search.
_CATALOG = {
    "bar": _ChipSpec(query="bar", take=15, urn="urn:tag:genre:place:restaurant:bar"),
    "cafe": _ChipSpec(query="cafe", take=25, urn="urn:tag:genre:place:restaurant:cafe"),
    "ceramics": _ChipSpec(query="ceramics", take=25, urn="urn:tag:genre:place:ceramics"),
    "gallery": _ChipSpec(query="gallery", take=25, urn="urn:tag:genre:place:art_gallery"),
}

_ALIASES = {
    "bar": "bar",
    "bars": "bar",
    "bar and restaurant": "bar",
    "bars and restaurants": "bar",
    "cafe": "cafe",
    "cafes": "cafe",
    "coffee": "cafe",
    "coffee shop": "cafe",
    "coffee shops": "cafe",
    "ceramics": "ceramics",
    "ceramic studio": "ceramics",
    "ceramic studios": "ceramics",
    "pottery": "ceramics",
    "gallery": "gallery",
    "galleries": "gallery",
    "art gallery": "gallery",
    "art galleries": "gallery",
}


async def resolve_tags(
    client: QlooClient,
    chips: Sequence[str],
    *,
    allow_list: Sequence[str] = ALLOWED_NAMESPACES,
) -> TagResolution:
    """Split the chips into verified tag URNs and explicit misses."""
    entries = [chip.strip() if chip else "" for chip in chips]
    if not entries:
        return TagResolution(
            error_code=ErrorCode.VALIDATION,
            error_message="no chips supplied",
        )

    resolved: list[ResolvedChipOut] = []
    unresolved: list[UnresolvedChipOut] = []
    evidence: list[CallRecord] = []

    for chip in entries:
        if not chip:
            unresolved.append(UnresolvedChipOut(chip=chip, reason="empty chip"))
            continue
        if chip.startswith("urn:tag:"):
            _resolve_literal(chip, allow_list, resolved, unresolved)
            continue
        spec = _CATALOG.get(_ALIASES.get(normalize_text(chip), ""))
        if spec is not None:
            response = await client.tags(spec.query, tag_types=[_TAG_NAMESPACE], take=spec.take)
            if response.call is not None:
                evidence.append(response.call)
            outcome: ResolvedChipOut | UnresolvedChipOut = _resolve_preset(
                chip, spec, response.rows, allow_list
            )
        else:
            response = await client.tags(chip, tag_types=[_TAG_NAMESPACE], take=FREE_TEXT_TAKE)
            if response.call is not None:
                evidence.append(response.call)
            outcome = _resolve_free_text(chip, response.rows, allow_list)
        if isinstance(outcome, ResolvedChipOut):
            resolved.append(outcome)
        else:
            unresolved.append(outcome)

    return TagResolution(
        resolved=resolved,
        unresolved=unresolved,
        error_code=ErrorCode.UNSPECIFIED,
        evidence=evidence,
    )


def _resolve_preset(
    chip: str,
    spec: _ChipSpec,
    rows: Sequence[CatalogTag],
    allow_list: Sequence[str],
) -> ResolvedChipOut | UnresolvedChipOut:
    """A preset chip resolves only through its verified URN in the result."""
    if not _allowed(spec.urn, allow_list):
        return UnresolvedChipOut(chip=chip, reason="outside the allow-list")
    for index, row in enumerate(rows):
        if row.id == spec.urn:
            return _accepted(chip, row, rank=index + 1, query=spec.query, free_text=False)
    return UnresolvedChipOut(chip=chip, reason=f"tag search did not return {spec.urn}")


def _resolve_free_text(
    chip: str,
    rows: Sequence[CatalogTag],
    allow_list: Sequence[str],
) -> ResolvedChipOut | UnresolvedChipOut:
    """Free text needs a confident allow-listed hit; ranks count among those."""
    allowed = [row for row in rows if _allowed(row.id, allow_list)]
    if not allowed:
        reason = "no confident hit" if not rows else "outside the allow-list"
        return UnresolvedChipOut(chip=chip, reason=reason)
    for index, row in enumerate(allowed):
        confidence = derived_confidence(chip, row.name, index + 1)
        if confidence >= LOW_CONFIDENCE:
            return _accepted(chip, row, rank=index + 1, query=chip, free_text=True)
    return UnresolvedChipOut(chip=chip, reason="no confident hit")


def _resolve_literal(
    urn: str,
    allow_list: Sequence[str],
    resolved: list[ResolvedChipOut],
    unresolved: list[UnresolvedChipOut],
) -> None:
    """A chip that already is a URN needs no search — only the allow-list."""
    if not _allowed(urn, allow_list):
        unresolved.append(UnresolvedChipOut(chip=urn, reason="outside the allow-list"))
        return
    tail = urn.split(":")[-1].replace("_", " ")
    resolved.append(
        ResolvedChipOut(
            chip=urn,
            urn=urn,
            label=tail.capitalize(),
            type=_namespace_of(urn, allow_list) or "",
            confidence=1.0,
            free_text=False,
        )
    )


def _accepted(
    chip: str,
    row: CatalogTag,
    *,
    rank: int,
    query: str,
    free_text: bool,
) -> ResolvedChipOut:
    return ResolvedChipOut(
        chip=chip,
        urn=row.id,
        label=row.name,
        type=row.type or "",
        confidence=derived_confidence(query, row.name, rank),
        free_text=free_text,
    )


def _allowed(urn: str | None, allow_list: Sequence[str]) -> bool:
    if not urn:
        return False
    return any(urn == namespace or urn.startswith(f"{namespace}:") for namespace in allow_list)


def _namespace_of(urn: str, allow_list: Sequence[str]) -> str | None:
    for namespace in allow_list:
        if urn == namespace or urn.startswith(f"{namespace}:"):
            return namespace
    return None
