"""gRPC servicer for TasteService.

HTTP ``/health`` stays on the FastAPI port. This server listens beside it so
the gateway can cancel an in-flight scout when the client aborts the job.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from concurrent import futures

import grpc

from karum.common.v1 import common_pb2
from karum.taste.v1 import taste_pb2, taste_pb2_grpc
from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode
from karum_service_taste.taste.compare import compare_audiences
from karum_service_taste.taste.doors import scout_doors
from karum_service_taste.taste.heatmap import locality_heatmap
from karum_service_taste.taste.schemas import (
    EntityRefOut,
    HeatmapResult,
    ScoutResult,
    SeedResolution,
    TagResolution,
)
from karum_service_taste.taste.seed import resolve_brand_seed
from karum_service_taste.taste.tags import resolve_tags


def _code(code: ErrorCode) -> int:
    return common_pb2.ErrorCode.Value(code.proto_name)


def _entity(ref: EntityRefOut | None) -> common_pb2.EntityRef:
    if ref is None:
        return common_pb2.EntityRef()
    place = None
    if ref.place is not None:
        location = None
        if ref.place.lat is not None and ref.place.lon is not None:
            location = common_pb2.GeoPoint(latitude=ref.place.lat, longitude=ref.place.lon)
        place = common_pb2.PlaceFacts(
            address=ref.place.address,
            website=ref.place.website,
            phone=ref.place.phone,
            hours=ref.place.hours,
            is_closed=ref.place.is_closed,
            location=location,
        )
    return common_pb2.EntityRef(
        id=ref.id, type=ref.type, name=ref.name, city=ref.city or "", place=place
    )


def _refs(items: Sequence) -> list[EntityRefOut]:
    out: list[EntityRefOut] = []
    for item in items:
        out.append(
            EntityRefOut(
                id=item.id,
                type=item.type or "urn:entity:place",
                name=item.name,
                city=item.city or None,
            )
        )
    return out


def _score(score) -> common_pb2.SubScore:
    if score is None:
        return common_pb2.SubScore()
    return common_pb2.SubScore(
        name=score.name, value=score.value, raw_value=score.raw_value, inputs=list(score.inputs)
    )


def _tag(tag) -> common_pb2.Tag:
    return common_pb2.Tag(urn=tag.urn, label=tag.label, type=getattr(tag, "type", "") or "")


_SKIP = {
    "low_affinity": taste_pb2.SKIP_REASON_CODE_LOW_AFFINITY,
    "competitor_saturation": taste_pb2.SKIP_REASON_CODE_COMPETITOR_SATURATION,
    "closed": taste_pb2.SKIP_REASON_CODE_CLOSED,
    "outside_city": taste_pb2.SKIP_REASON_CODE_OUTSIDE_CITY,
    "unresolved": taste_pb2.SKIP_REASON_CODE_UNRESOLVED,
}


def _evidence(records: Sequence, prefix: str = "ev") -> list[common_pb2.EvidenceCall]:
    calls = []
    for index, record in enumerate(records, start=1):
        calls.append(
            common_pb2.EvidenceCall(
                id=f"{prefix}-{index:04d}",
                endpoint=getattr(record, "endpoint", "") or "",
                parameters=getattr(record, "parameters", "") or "",
                result_count=int(getattr(record, "rows", 0) or 0),
                latency_ms=int(getattr(record, "duration_ms", 0) or 0),
            )
        )
    return calls


def scout_message(result: ScoutResult) -> taste_pb2.ScoutDoorsResponse:
    """Translate a scout result onto the frozen proto."""
    doors = []
    for door in result.doors:
        doors.append(
            taste_pb2.DoorCandidate(
                entity=_entity(door.entity),
                affinity=_score(door.affinity),
                demographic_alignment=_score(door.demographic_alignment)
                if door.demographic_alignment
                else None,
                shared_tags=[_tag(tag) for tag in door.shared_tags],
                explainability=[
                    taste_pb2.ExplainabilityContribution(
                        entity_id=item.entity_id, score=item.score, label=item.label
                    )
                    for item in door.explainability
                ],
                distance_meters=door.distance_meters or 0,
                outside_city=door.outside_city,
                rank=door.rank,
                evidence_ids=list(door.evidence_ids),
            )
        )
    skips = []
    for item in result.skip_list:
        skips.append(
            taste_pb2.SkipItem(
                entity=_entity(item.entity),
                affinity=_score(item.affinity),
                reason=_SKIP.get(item.reason.value, taste_pb2.SKIP_REASON_CODE_LOW_AFFINITY),
                reason_detail=item.reason_detail,
                floor=item.floor,
            )
        )
    return taste_pb2.ScoutDoorsResponse(
        doors=doors,
        skip_list=skips,
        warnings=list(result.warnings),
        error_code=_code(result.error_code),
        error_message=result.error_message,
        evidence=_evidence(result.evidence),
        affinity_floor=result.affinity_floor,
    )


def seed_message(result: SeedResolution) -> taste_pb2.ResolveBrandSeedResponse:
    return taste_pb2.ResolveBrandSeedResponse(
        candidates=[
            taste_pb2.SeedCandidate(
                entity=_entity(item.entity),
                confidence=item.confidence,
                ambiguous=item.ambiguous,
                in_city=item.in_city,
                matched_query=item.matched_query,
            )
            for item in result.candidates
        ],
        confidence=result.confidence,
        unresolved=result.unresolved,
        error_code=_code(result.error_code),
        error_message=result.error_message,
        evidence=_evidence(result.evidence),
    )


def tags_message(result: TagResolution) -> taste_pb2.ResolveTagsResponse:
    return taste_pb2.ResolveTagsResponse(
        resolved=[
            taste_pb2.ResolvedTag(
                chip=item.chip,
                tag=common_pb2.Tag(urn=item.urn, label=item.label, type=item.type),
                confidence=item.confidence,
                free_text=item.free_text,
            )
            for item in result.resolved
        ],
        unresolved=[
            taste_pb2.UnresolvedTag(chip=item.chip, reason=item.reason)
            for item in result.unresolved
        ],
        error_code=_code(result.error_code),
        error_message=result.error_message,
        evidence=_evidence(result.evidence),
    )


def _geo(point) -> common_pb2.GeoPoint | None:
    if point is None:
        return None
    return common_pb2.GeoPoint(latitude=point.lat, longitude=point.lon)


def heatmap_message(result: HeatmapResult) -> taste_pb2.GetLocalityHeatmapResponse:
    return taste_pb2.GetLocalityHeatmapResponse(
        corridors=list(result.corridors),
        anchors=[_entity(item) for item in result.anchors],
        available=result.available,
        unavailable_reason=result.unavailable_reason,
        error_code=_code(result.error_code),
        error_message=result.error_message,
        evidence=_evidence(result.evidence),
        cells=[
            taste_pb2.HeatmapPoint(
                location=_geo(cell.location),
                geohash=cell.geohash or "",
                affinity=cell.affinity or 0,
                affinity_rank=int(cell.affinity_rank or 0),
                popularity=cell.popularity or 0,
            )
            for cell in result.cells
        ],
        localities=[
            taste_pb2.LocalityCluster(
                name=item.name,
                centroid=_geo(item.centroid),
                polygon=[
                    point
                    for point in (_geo(vertex) for vertex in item.polygon)
                    if point is not None
                ],
                affinity=item.affinity or 0,
            )
            for item in result.localities
        ],
    )


class TasteServicer(taste_pb2_grpc.TasteServiceServicer):
    """Adapts the in-process taste functions onto the gRPC contract.

    All RPCs share one event loop running on a background thread. The Qloo
    client opens a pooled ``httpx.AsyncClient`` lazily on first use, so it must
    stay on the loop that created it; ``asyncio.run`` per RPC closes that loop
    and poisons the pool for every later call.
    """

    def __init__(self, client: QlooClient) -> None:
        self.client = client
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="taste-grpc-loop",
            daemon=True,
        )
        self._loop_thread.start()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def ResolveBrandSeed(self, request, context):  # noqa: N802
        location = None
        if request.HasField("location"):
            location = (request.location.latitude, request.location.longitude)
        result = self._run(
            resolve_brand_seed(
                self.client,
                request.brand_query,
                fallback_queries=list(request.fallback_queries),
                location=location,
                city=request.city or None,
                take=request.take or 5,
            )
        )
        return seed_message(result)

    def ResolveTags(self, request, context):  # noqa: N802
        return tags_message(self._run(resolve_tags(self.client, list(request.chips))))

    def ScoutDoors(self, request, context):  # noqa: N802
        seed = _refs(request.seed.entities)
        location = (request.location.latitude, request.location.longitude)
        tags = [tag.urn for tag in request.category_tags if tag.urn]
        result = self._run(
            scout_doors(
                self.client,
                seed,
                location=location,
                radius_meters=request.radius_meters,
                category_tags=tags,
                skip_candidate_ids=list(request.skip_candidate_ids),
                skip_candidate_names=list(request.skip_candidate_names),
                fanout_limit=self.client.fanout_cap,
            )
        )
        return scout_message(result)

    def GetLocalityHeatmap(self, request, context):  # noqa: N802
        result = self._run(
            locality_heatmap(
                self.client,
                _refs(request.entities),
                location=(request.location.latitude, request.location.longitude),
                radius_meters=request.radius_meters,
                include_localities=request.include_localities,
            )
        )
        return heatmap_message(result)

    def CompareAudiences(self, request, context):  # noqa: N802
        from karum_service_taste.taste.schemas import CompareResult

        brand_id = request.emerging_brand.id
        venue_id = request.venue.id
        if not venue_id or not brand_id:
            empty = CompareResult(
                available=False,
                unavailable_reason="compare needs a venue id and a brand id",
                error_code=ErrorCode.VALIDATION,
                error_message="compare needs a venue id and a brand id",
            )
            return _compare_message(empty)
        result = self._run(compare_audiences(self.client, venue_id, brand_id))
        return _compare_message(result)


def _compare_message(result) -> taste_pb2.CompareAudiencesResponse:
    return taste_pb2.CompareAudiencesResponse(
        overlap_tags=[_tag(tag) for tag in result.overlap_tags],
        match_entities=[_entity(item) for item in result.match_entities],
        match_entities_present=bool(result.match_entities),
        available=result.available,
        unavailable_reason=result.unavailable_reason,
        error_code=_code(result.error_code),
        error_message=result.error_message,
        evidence=_evidence(result.evidence),
    )


def serve(client: QlooClient, port: int) -> grpc.Server:
    """Start the taste gRPC server on ``port`` and return it still running."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    taste_pb2_grpc.add_TasteServiceServicer_to_server(TasteServicer(client), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    return server
