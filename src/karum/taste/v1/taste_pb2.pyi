from karum.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SkipReasonCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SKIP_REASON_CODE_UNSPECIFIED: _ClassVar[SkipReasonCode]
    SKIP_REASON_CODE_LOW_AFFINITY: _ClassVar[SkipReasonCode]
    SKIP_REASON_CODE_COMPETITOR_SATURATION: _ClassVar[SkipReasonCode]
    SKIP_REASON_CODE_CLOSED: _ClassVar[SkipReasonCode]
    SKIP_REASON_CODE_OUTSIDE_CITY: _ClassVar[SkipReasonCode]
    SKIP_REASON_CODE_UNRESOLVED: _ClassVar[SkipReasonCode]
SKIP_REASON_CODE_UNSPECIFIED: SkipReasonCode
SKIP_REASON_CODE_LOW_AFFINITY: SkipReasonCode
SKIP_REASON_CODE_COMPETITOR_SATURATION: SkipReasonCode
SKIP_REASON_CODE_CLOSED: SkipReasonCode
SKIP_REASON_CODE_OUTSIDE_CITY: SkipReasonCode
SKIP_REASON_CODE_UNRESOLVED: SkipReasonCode

class SeedQuery(_message.Message):
    __slots__ = ("text", "matches", "resolved", "note")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    MATCHES_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_FIELD_NUMBER: _ClassVar[int]
    NOTE_FIELD_NUMBER: _ClassVar[int]
    text: str
    matches: _containers.RepeatedCompositeFieldContainer[_common_pb2.EntityRef]
    resolved: bool
    note: str
    def __init__(self, text: _Optional[str] = ..., matches: _Optional[_Iterable[_Union[_common_pb2.EntityRef, _Mapping]]] = ..., resolved: _Optional[bool] = ..., note: _Optional[str] = ...) -> None: ...

class BrandSeed(_message.Message):
    __slots__ = ("brand_text", "entities", "tags", "queries", "confidence", "partial")
    BRAND_TEXT_FIELD_NUMBER: _ClassVar[int]
    ENTITIES_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    QUERIES_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    PARTIAL_FIELD_NUMBER: _ClassVar[int]
    brand_text: str
    entities: _containers.RepeatedCompositeFieldContainer[_common_pb2.EntityRef]
    tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    queries: _containers.RepeatedCompositeFieldContainer[SeedQuery]
    confidence: float
    partial: bool
    def __init__(self, brand_text: _Optional[str] = ..., entities: _Optional[_Iterable[_Union[_common_pb2.EntityRef, _Mapping]]] = ..., tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., queries: _Optional[_Iterable[_Union[SeedQuery, _Mapping]]] = ..., confidence: _Optional[float] = ..., partial: _Optional[bool] = ...) -> None: ...

class SeedCandidate(_message.Message):
    __slots__ = ("entity", "confidence", "ambiguous", "in_city", "matched_query")
    ENTITY_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    AMBIGUOUS_FIELD_NUMBER: _ClassVar[int]
    IN_CITY_FIELD_NUMBER: _ClassVar[int]
    MATCHED_QUERY_FIELD_NUMBER: _ClassVar[int]
    entity: _common_pb2.EntityRef
    confidence: float
    ambiguous: bool
    in_city: bool
    matched_query: str
    def __init__(self, entity: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., confidence: _Optional[float] = ..., ambiguous: _Optional[bool] = ..., in_city: _Optional[bool] = ..., matched_query: _Optional[str] = ...) -> None: ...

class ResolveBrandSeedRequest(_message.Message):
    __slots__ = ("meta", "brand_query", "fallback_queries", "location", "city", "take")
    META_FIELD_NUMBER: _ClassVar[int]
    BRAND_QUERY_FIELD_NUMBER: _ClassVar[int]
    FALLBACK_QUERIES_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    TAKE_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    brand_query: str
    fallback_queries: _containers.RepeatedScalarFieldContainer[str]
    location: _common_pb2.GeoPoint
    city: str
    take: int
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., brand_query: _Optional[str] = ..., fallback_queries: _Optional[_Iterable[str]] = ..., location: _Optional[_Union[_common_pb2.GeoPoint, _Mapping]] = ..., city: _Optional[str] = ..., take: _Optional[int] = ...) -> None: ...

class ResolveBrandSeedResponse(_message.Message):
    __slots__ = ("candidates", "confidence", "unresolved", "error_code", "error_message", "evidence")
    CANDIDATES_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    UNRESOLVED_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    candidates: _containers.RepeatedCompositeFieldContainer[SeedCandidate]
    confidence: float
    unresolved: bool
    error_code: _common_pb2.ErrorCode
    error_message: str
    evidence: _containers.RepeatedCompositeFieldContainer[_common_pb2.EvidenceCall]
    def __init__(self, candidates: _Optional[_Iterable[_Union[SeedCandidate, _Mapping]]] = ..., confidence: _Optional[float] = ..., unresolved: _Optional[bool] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[_common_pb2.EvidenceCall, _Mapping]]] = ...) -> None: ...

class ResolvedTag(_message.Message):
    __slots__ = ("chip", "tag", "confidence", "free_text")
    CHIP_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    FREE_TEXT_FIELD_NUMBER: _ClassVar[int]
    chip: str
    tag: _common_pb2.Tag
    confidence: float
    free_text: bool
    def __init__(self, chip: _Optional[str] = ..., tag: _Optional[_Union[_common_pb2.Tag, _Mapping]] = ..., confidence: _Optional[float] = ..., free_text: _Optional[bool] = ...) -> None: ...

class UnresolvedTag(_message.Message):
    __slots__ = ("chip", "reason")
    CHIP_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    chip: str
    reason: str
    def __init__(self, chip: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class ResolveTagsRequest(_message.Message):
    __slots__ = ("meta", "chips")
    META_FIELD_NUMBER: _ClassVar[int]
    CHIPS_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    chips: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., chips: _Optional[_Iterable[str]] = ...) -> None: ...

class ResolveTagsResponse(_message.Message):
    __slots__ = ("resolved", "unresolved", "error_code", "error_message", "evidence")
    RESOLVED_FIELD_NUMBER: _ClassVar[int]
    UNRESOLVED_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    resolved: _containers.RepeatedCompositeFieldContainer[ResolvedTag]
    unresolved: _containers.RepeatedCompositeFieldContainer[UnresolvedTag]
    error_code: _common_pb2.ErrorCode
    error_message: str
    evidence: _containers.RepeatedCompositeFieldContainer[_common_pb2.EvidenceCall]
    def __init__(self, resolved: _Optional[_Iterable[_Union[ResolvedTag, _Mapping]]] = ..., unresolved: _Optional[_Iterable[_Union[UnresolvedTag, _Mapping]]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[_common_pb2.EvidenceCall, _Mapping]]] = ...) -> None: ...

class ExplainabilityContribution(_message.Message):
    __slots__ = ("entity_id", "score", "label")
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    entity_id: str
    score: float
    label: str
    def __init__(self, entity_id: _Optional[str] = ..., score: _Optional[float] = ..., label: _Optional[str] = ...) -> None: ...

class DemographicBucket(_message.Message):
    __slots__ = ("label", "delta")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    DELTA_FIELD_NUMBER: _ClassVar[int]
    label: str
    delta: float
    def __init__(self, label: _Optional[str] = ..., delta: _Optional[float] = ...) -> None: ...

class DemographicProfile(_message.Message):
    __slots__ = ("age_buckets", "male_delta", "female_delta")
    AGE_BUCKETS_FIELD_NUMBER: _ClassVar[int]
    MALE_DELTA_FIELD_NUMBER: _ClassVar[int]
    FEMALE_DELTA_FIELD_NUMBER: _ClassVar[int]
    age_buckets: _containers.RepeatedCompositeFieldContainer[DemographicBucket]
    male_delta: float
    female_delta: float
    def __init__(self, age_buckets: _Optional[_Iterable[_Union[DemographicBucket, _Mapping]]] = ..., male_delta: _Optional[float] = ..., female_delta: _Optional[float] = ...) -> None: ...

class DoorCandidate(_message.Message):
    __slots__ = ("entity", "affinity", "demographic_alignment", "shared_tags", "explainability", "demographics", "distance_meters", "outside_city", "rank", "evidence_ids")
    ENTITY_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_FIELD_NUMBER: _ClassVar[int]
    DEMOGRAPHIC_ALIGNMENT_FIELD_NUMBER: _ClassVar[int]
    SHARED_TAGS_FIELD_NUMBER: _ClassVar[int]
    EXPLAINABILITY_FIELD_NUMBER: _ClassVar[int]
    DEMOGRAPHICS_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_METERS_FIELD_NUMBER: _ClassVar[int]
    OUTSIDE_CITY_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_IDS_FIELD_NUMBER: _ClassVar[int]
    entity: _common_pb2.EntityRef
    affinity: _common_pb2.SubScore
    demographic_alignment: _common_pb2.SubScore
    shared_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    explainability: _containers.RepeatedCompositeFieldContainer[ExplainabilityContribution]
    demographics: DemographicProfile
    distance_meters: float
    outside_city: bool
    rank: int
    evidence_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, entity: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., affinity: _Optional[_Union[_common_pb2.SubScore, _Mapping]] = ..., demographic_alignment: _Optional[_Union[_common_pb2.SubScore, _Mapping]] = ..., shared_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., explainability: _Optional[_Iterable[_Union[ExplainabilityContribution, _Mapping]]] = ..., demographics: _Optional[_Union[DemographicProfile, _Mapping]] = ..., distance_meters: _Optional[float] = ..., outside_city: _Optional[bool] = ..., rank: _Optional[int] = ..., evidence_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class SkipItem(_message.Message):
    __slots__ = ("entity", "affinity", "reason", "reason_detail", "competitor_count")
    ENTITY_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    REASON_DETAIL_FIELD_NUMBER: _ClassVar[int]
    COMPETITOR_COUNT_FIELD_NUMBER: _ClassVar[int]
    entity: _common_pb2.EntityRef
    affinity: _common_pb2.SubScore
    reason: SkipReasonCode
    reason_detail: str
    competitor_count: int
    def __init__(self, entity: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., affinity: _Optional[_Union[_common_pb2.SubScore, _Mapping]] = ..., reason: _Optional[_Union[SkipReasonCode, str]] = ..., reason_detail: _Optional[str] = ..., competitor_count: _Optional[int] = ...) -> None: ...

class ScoutDoorsRequest(_message.Message):
    __slots__ = ("meta", "seed", "tags", "location", "radius_meters", "category_tags")
    META_FIELD_NUMBER: _ClassVar[int]
    SEED_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    RADIUS_METERS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_TAGS_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    seed: BrandSeed
    tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    location: _common_pb2.GeoPoint
    radius_meters: int
    category_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., seed: _Optional[_Union[BrandSeed, _Mapping]] = ..., tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., location: _Optional[_Union[_common_pb2.GeoPoint, _Mapping]] = ..., radius_meters: _Optional[int] = ..., category_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ...) -> None: ...

class ScoutDoorsResponse(_message.Message):
    __slots__ = ("doors", "skip_list", "warnings", "error_code", "error_message", "evidence")
    DOORS_FIELD_NUMBER: _ClassVar[int]
    SKIP_LIST_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    doors: _containers.RepeatedCompositeFieldContainer[DoorCandidate]
    skip_list: _containers.RepeatedCompositeFieldContainer[SkipItem]
    warnings: _containers.RepeatedScalarFieldContainer[str]
    error_code: _common_pb2.ErrorCode
    error_message: str
    evidence: _containers.RepeatedCompositeFieldContainer[_common_pb2.EvidenceCall]
    def __init__(self, doors: _Optional[_Iterable[_Union[DoorCandidate, _Mapping]]] = ..., skip_list: _Optional[_Iterable[_Union[SkipItem, _Mapping]]] = ..., warnings: _Optional[_Iterable[str]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[_common_pb2.EvidenceCall, _Mapping]]] = ...) -> None: ...

class HeatmapPoint(_message.Message):
    __slots__ = ("location", "geohash", "affinity", "affinity_rank", "popularity")
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    GEOHASH_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_RANK_FIELD_NUMBER: _ClassVar[int]
    POPULARITY_FIELD_NUMBER: _ClassVar[int]
    location: _common_pb2.GeoPoint
    geohash: str
    affinity: float
    affinity_rank: int
    popularity: float
    def __init__(self, location: _Optional[_Union[_common_pb2.GeoPoint, _Mapping]] = ..., geohash: _Optional[str] = ..., affinity: _Optional[float] = ..., affinity_rank: _Optional[int] = ..., popularity: _Optional[float] = ...) -> None: ...

class LocalityCluster(_message.Message):
    __slots__ = ("name", "centroid", "polygon", "affinity")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CENTROID_FIELD_NUMBER: _ClassVar[int]
    POLYGON_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_FIELD_NUMBER: _ClassVar[int]
    name: str
    centroid: _common_pb2.GeoPoint
    polygon: _containers.RepeatedCompositeFieldContainer[_common_pb2.GeoPoint]
    affinity: float
    def __init__(self, name: _Optional[str] = ..., centroid: _Optional[_Union[_common_pb2.GeoPoint, _Mapping]] = ..., polygon: _Optional[_Iterable[_Union[_common_pb2.GeoPoint, _Mapping]]] = ..., affinity: _Optional[float] = ...) -> None: ...

class GetLocalityHeatmapRequest(_message.Message):
    __slots__ = ("meta", "entities", "location", "radius_meters", "include_localities")
    META_FIELD_NUMBER: _ClassVar[int]
    ENTITIES_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    RADIUS_METERS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_LOCALITIES_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    entities: _containers.RepeatedCompositeFieldContainer[_common_pb2.EntityRef]
    location: _common_pb2.GeoPoint
    radius_meters: int
    include_localities: bool
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., entities: _Optional[_Iterable[_Union[_common_pb2.EntityRef, _Mapping]]] = ..., location: _Optional[_Union[_common_pb2.GeoPoint, _Mapping]] = ..., radius_meters: _Optional[int] = ..., include_localities: _Optional[bool] = ...) -> None: ...

class GetLocalityHeatmapResponse(_message.Message):
    __slots__ = ("cells", "localities", "corridors", "anchors", "available", "unavailable_reason", "error_code", "error_message", "evidence")
    CELLS_FIELD_NUMBER: _ClassVar[int]
    LOCALITIES_FIELD_NUMBER: _ClassVar[int]
    CORRIDORS_FIELD_NUMBER: _ClassVar[int]
    ANCHORS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    UNAVAILABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    cells: _containers.RepeatedCompositeFieldContainer[HeatmapPoint]
    localities: _containers.RepeatedCompositeFieldContainer[LocalityCluster]
    corridors: _containers.RepeatedScalarFieldContainer[str]
    anchors: _containers.RepeatedCompositeFieldContainer[_common_pb2.EntityRef]
    available: bool
    unavailable_reason: str
    error_code: _common_pb2.ErrorCode
    error_message: str
    evidence: _containers.RepeatedCompositeFieldContainer[_common_pb2.EvidenceCall]
    def __init__(self, cells: _Optional[_Iterable[_Union[HeatmapPoint, _Mapping]]] = ..., localities: _Optional[_Iterable[_Union[LocalityCluster, _Mapping]]] = ..., corridors: _Optional[_Iterable[str]] = ..., anchors: _Optional[_Iterable[_Union[_common_pb2.EntityRef, _Mapping]]] = ..., available: _Optional[bool] = ..., unavailable_reason: _Optional[str] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[_common_pb2.EvidenceCall, _Mapping]]] = ...) -> None: ...

class CompareAudiencesRequest(_message.Message):
    __slots__ = ("meta", "emerging_brand", "venue", "incumbent_name")
    META_FIELD_NUMBER: _ClassVar[int]
    EMERGING_BRAND_FIELD_NUMBER: _ClassVar[int]
    VENUE_FIELD_NUMBER: _ClassVar[int]
    INCUMBENT_NAME_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    emerging_brand: _common_pb2.EntityRef
    venue: _common_pb2.EntityRef
    incumbent_name: str
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., emerging_brand: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., venue: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., incumbent_name: _Optional[str] = ...) -> None: ...

class CompareAudiencesResponse(_message.Message):
    __slots__ = ("overlap_tags", "match_entities", "match_entities_present", "available", "unavailable_reason", "error_code", "error_message", "evidence")
    OVERLAP_TAGS_FIELD_NUMBER: _ClassVar[int]
    MATCH_ENTITIES_FIELD_NUMBER: _ClassVar[int]
    MATCH_ENTITIES_PRESENT_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    UNAVAILABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    overlap_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    match_entities: _containers.RepeatedCompositeFieldContainer[_common_pb2.EntityRef]
    match_entities_present: bool
    available: bool
    unavailable_reason: str
    error_code: _common_pb2.ErrorCode
    error_message: str
    evidence: _containers.RepeatedCompositeFieldContainer[_common_pb2.EvidenceCall]
    def __init__(self, overlap_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., match_entities: _Optional[_Iterable[_Union[_common_pb2.EntityRef, _Mapping]]] = ..., match_entities_present: _Optional[bool] = ..., available: _Optional[bool] = ..., unavailable_reason: _Optional[str] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[_common_pb2.EvidenceCall, _Mapping]]] = ...) -> None: ...
