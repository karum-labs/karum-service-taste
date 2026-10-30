import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from karum.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CampaignMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CAMPAIGN_MODE_UNSPECIFIED: _ClassVar[CampaignMode]
    CAMPAIGN_MODE_WHOLESALE: _ClassVar[CampaignMode]
    CAMPAIGN_MODE_FLAGSHIP: _ClassVar[CampaignMode]
    CAMPAIGN_MODE_COLLAB: _ClassVar[CampaignMode]

class JobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATE_UNSPECIFIED: _ClassVar[JobState]
    JOB_STATE_RESOLVING: _ClassVar[JobState]
    JOB_STATE_RUNNING: _ClassVar[JobState]
    JOB_STATE_READY: _ClassVar[JobState]
    JOB_STATE_DEGRADED: _ClassVar[JobState]
    JOB_STATE_FAILED: _ClassVar[JobState]

class TraceStage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRACE_STAGE_UNSPECIFIED: _ClassVar[TraceStage]
    TRACE_STAGE_GEOCODE: _ClassVar[TraceStage]
    TRACE_STAGE_SEED_RESOLUTION: _ClassVar[TraceStage]
    TRACE_STAGE_TAG_RESOLUTION: _ClassVar[TraceStage]
    TRACE_STAGE_DOOR_RANKING: _ClassVar[TraceStage]
    TRACE_STAGE_DEMOGRAPHICS: _ClassVar[TraceStage]
    TRACE_STAGE_HEATMAP: _ClassVar[TraceStage]
    TRACE_STAGE_COMPARE: _ClassVar[TraceStage]
    TRACE_STAGE_MENU_GROUNDING: _ClassVar[TraceStage]
    TRACE_STAGE_PLACES: _ClassVar[TraceStage]
    TRACE_STAGE_SCORING: _ClassVar[TraceStage]
    TRACE_STAGE_ROUTE: _ClassVar[TraceStage]
    TRACE_STAGE_DRAFT: _ClassVar[TraceStage]
    TRACE_STAGE_BASELINE: _ClassVar[TraceStage]
    TRACE_STAGE_PERSIST: _ClassVar[TraceStage]

class TraceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRACE_STATUS_UNSPECIFIED: _ClassVar[TraceStatus]
    TRACE_STATUS_STARTED: _ClassVar[TraceStatus]
    TRACE_STATUS_FINISHED: _ClassVar[TraceStatus]
    TRACE_STATUS_FAILED: _ClassVar[TraceStatus]
    TRACE_STATUS_SKIPPED: _ClassVar[TraceStatus]
CAMPAIGN_MODE_UNSPECIFIED: CampaignMode
CAMPAIGN_MODE_WHOLESALE: CampaignMode
CAMPAIGN_MODE_FLAGSHIP: CampaignMode
CAMPAIGN_MODE_COLLAB: CampaignMode
JOB_STATE_UNSPECIFIED: JobState
JOB_STATE_RESOLVING: JobState
JOB_STATE_RUNNING: JobState
JOB_STATE_READY: JobState
JOB_STATE_DEGRADED: JobState
JOB_STATE_FAILED: JobState
TRACE_STAGE_UNSPECIFIED: TraceStage
TRACE_STAGE_GEOCODE: TraceStage
TRACE_STAGE_SEED_RESOLUTION: TraceStage
TRACE_STAGE_TAG_RESOLUTION: TraceStage
TRACE_STAGE_DOOR_RANKING: TraceStage
TRACE_STAGE_DEMOGRAPHICS: TraceStage
TRACE_STAGE_HEATMAP: TraceStage
TRACE_STAGE_COMPARE: TraceStage
TRACE_STAGE_MENU_GROUNDING: TraceStage
TRACE_STAGE_PLACES: TraceStage
TRACE_STAGE_SCORING: TraceStage
TRACE_STAGE_ROUTE: TraceStage
TRACE_STAGE_DRAFT: TraceStage
TRACE_STAGE_BASELINE: TraceStage
TRACE_STAGE_PERSIST: TraceStage
TRACE_STATUS_UNSPECIFIED: TraceStatus
TRACE_STATUS_STARTED: TraceStatus
TRACE_STATUS_FINISHED: TraceStatus
TRACE_STATUS_FAILED: TraceStatus
TRACE_STATUS_SKIPPED: TraceStatus

class ModelAttribution(_message.Message):
    __slots__ = ("model_id", "prompt_version", "evidence_ids", "ungrounded")
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    PROMPT_VERSION_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_IDS_FIELD_NUMBER: _ClassVar[int]
    UNGROUNDED_FIELD_NUMBER: _ClassVar[int]
    model_id: str
    prompt_version: str
    evidence_ids: _containers.RepeatedScalarFieldContainer[str]
    ungrounded: bool
    def __init__(self, model_id: _Optional[str] = ..., prompt_version: _Optional[str] = ..., evidence_ids: _Optional[_Iterable[str]] = ..., ungrounded: _Optional[bool] = ...) -> None: ...

class TraceEvent(_message.Message):
    __slots__ = ("id", "job_id", "trace_id", "sequence", "cursor", "stage", "status", "cache_hit", "elapsed_ms", "message", "occurred_at", "error_code")
    ID_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CACHE_HIT_FIELD_NUMBER: _ClassVar[int]
    ELAPSED_MS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    OCCURRED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    id: str
    job_id: str
    trace_id: str
    sequence: int
    cursor: str
    stage: TraceStage
    status: TraceStatus
    cache_hit: bool
    elapsed_ms: int
    message: str
    occurred_at: _timestamp_pb2.Timestamp
    error_code: _common_pb2.ErrorCode
    def __init__(self, id: _Optional[str] = ..., job_id: _Optional[str] = ..., trace_id: _Optional[str] = ..., sequence: _Optional[int] = ..., cursor: _Optional[str] = ..., stage: _Optional[_Union[TraceStage, str]] = ..., status: _Optional[_Union[TraceStatus, str]] = ..., cache_hit: _Optional[bool] = ..., elapsed_ms: _Optional[int] = ..., message: _Optional[str] = ..., occurred_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ...) -> None: ...

class Sku(_message.Message):
    __slots__ = ("id", "name")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class BrandContext(_message.Message):
    __slots__ = ("name", "skus", "category", "description", "positioning", "audience")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SKUS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    POSITIONING_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    name: str
    skus: _containers.RepeatedCompositeFieldContainer[Sku]
    category: str
    description: str
    positioning: str
    audience: str
    def __init__(self, name: _Optional[str] = ..., skus: _Optional[_Iterable[_Union[Sku, _Mapping]]] = ..., category: _Optional[str] = ..., description: _Optional[str] = ..., positioning: _Optional[str] = ..., audience: _Optional[str] = ...) -> None: ...

class GroundingSource(_message.Message):
    __slots__ = ("url", "title")
    URL_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    url: str
    title: str
    def __init__(self, url: _Optional[str] = ..., title: _Optional[str] = ...) -> None: ...

class Incumbent(_message.Message):
    __slots__ = ("name", "sources")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    name: str
    sources: _containers.RepeatedCompositeFieldContainer[GroundingSource]
    def __init__(self, name: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[GroundingSource, _Mapping]]] = ...) -> None: ...

class MenuAuditTarget(_message.Message):
    __slots__ = ("door", "website", "taste_tags", "skip_candidate", "qloo_incumbent_names")
    DOOR_FIELD_NUMBER: _ClassVar[int]
    WEBSITE_FIELD_NUMBER: _ClassVar[int]
    TASTE_TAGS_FIELD_NUMBER: _ClassVar[int]
    SKIP_CANDIDATE_FIELD_NUMBER: _ClassVar[int]
    QLOO_INCUMBENT_NAMES_FIELD_NUMBER: _ClassVar[int]
    door: _common_pb2.EntityRef
    website: str
    taste_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    skip_candidate: bool
    qloo_incumbent_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, door: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., website: _Optional[str] = ..., taste_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., skip_candidate: _Optional[bool] = ..., qloo_incumbent_names: _Optional[_Iterable[str]] = ...) -> None: ...

class MenuAuditResult(_message.Message):
    __slots__ = ("door", "succeeded", "shelf_unknown", "incumbents", "competitor_count", "shelf_opportunity", "menu_summary", "sources")
    DOOR_FIELD_NUMBER: _ClassVar[int]
    SUCCEEDED_FIELD_NUMBER: _ClassVar[int]
    SHELF_UNKNOWN_FIELD_NUMBER: _ClassVar[int]
    INCUMBENTS_FIELD_NUMBER: _ClassVar[int]
    COMPETITOR_COUNT_FIELD_NUMBER: _ClassVar[int]
    SHELF_OPPORTUNITY_FIELD_NUMBER: _ClassVar[int]
    MENU_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    door: _common_pb2.EntityRef
    succeeded: bool
    shelf_unknown: bool
    incumbents: _containers.RepeatedCompositeFieldContainer[Incumbent]
    competitor_count: int
    shelf_opportunity: float
    menu_summary: str
    sources: _containers.RepeatedCompositeFieldContainer[GroundingSource]
    def __init__(self, door: _Optional[_Union[_common_pb2.EntityRef, _Mapping]] = ..., succeeded: _Optional[bool] = ..., shelf_unknown: _Optional[bool] = ..., incumbents: _Optional[_Iterable[_Union[Incumbent, _Mapping]]] = ..., competitor_count: _Optional[int] = ..., shelf_opportunity: _Optional[float] = ..., menu_summary: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[GroundingSource, _Mapping]]] = ...) -> None: ...

class AuditMenuRequest(_message.Message):
    __slots__ = ("meta", "mode", "targets")
    META_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    TARGETS_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    mode: CampaignMode
    targets: _containers.RepeatedCompositeFieldContainer[MenuAuditTarget]
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., mode: _Optional[_Union[CampaignMode, str]] = ..., targets: _Optional[_Iterable[_Union[MenuAuditTarget, _Mapping]]] = ...) -> None: ...

class AuditMenuResponse(_message.Message):
    __slots__ = ("results", "attribution", "error_code", "error_message")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[MenuAuditResult]
    attribution: ModelAttribution
    error_code: _common_pb2.ErrorCode
    error_message: str
    def __init__(self, results: _Optional[_Iterable[_Union[MenuAuditResult, _Mapping]]] = ..., attribution: _Optional[_Union[ModelAttribution, _Mapping]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class DoorContext(_message.Message):
    __slots__ = ("shared_tags", "affinity", "compare_tags", "audit")
    SHARED_TAGS_FIELD_NUMBER: _ClassVar[int]
    AFFINITY_FIELD_NUMBER: _ClassVar[int]
    COMPARE_TAGS_FIELD_NUMBER: _ClassVar[int]
    AUDIT_FIELD_NUMBER: _ClassVar[int]
    shared_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    affinity: _common_pb2.SubScore
    compare_tags: _containers.RepeatedCompositeFieldContainer[_common_pb2.Tag]
    audit: MenuAuditResult
    def __init__(self, shared_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., affinity: _Optional[_Union[_common_pb2.SubScore, _Mapping]] = ..., compare_tags: _Optional[_Iterable[_Union[_common_pb2.Tag, _Mapping]]] = ..., audit: _Optional[_Union[MenuAuditResult, _Mapping]] = ...) -> None: ...

class Citation(_message.Message):
    __slots__ = ("evidence_id", "text")
    EVIDENCE_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    evidence_id: str
    text: str
    def __init__(self, evidence_id: _Optional[str] = ..., text: _Optional[str] = ...) -> None: ...

class Battlecard(_message.Message):
    __slots__ = ("headline", "incumbent_name", "talking_points", "compare_summary")
    HEADLINE_FIELD_NUMBER: _ClassVar[int]
    INCUMBENT_NAME_FIELD_NUMBER: _ClassVar[int]
    TALKING_POINTS_FIELD_NUMBER: _ClassVar[int]
    COMPARE_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    headline: str
    incumbent_name: str
    talking_points: _containers.RepeatedScalarFieldContainer[str]
    compare_summary: str
    def __init__(self, headline: _Optional[str] = ..., incumbent_name: _Optional[str] = ..., talking_points: _Optional[_Iterable[str]] = ..., compare_summary: _Optional[str] = ...) -> None: ...

class DraftDoorPitchRequest(_message.Message):
    __slots__ = ("meta", "mode", "brand", "door", "city", "max_words", "evidence_ids", "instructions", "attachment_id", "attachment_name")
    META_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    BRAND_FIELD_NUMBER: _ClassVar[int]
    DOOR_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    MAX_WORDS_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_IDS_FIELD_NUMBER: _ClassVar[int]
    INSTRUCTIONS_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_ID_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENT_NAME_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    mode: CampaignMode
    brand: BrandContext
    door: DoorContext
    city: str
    max_words: int
    evidence_ids: _containers.RepeatedScalarFieldContainer[str]
    instructions: str
    attachment_id: str
    attachment_name: str
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., mode: _Optional[_Union[CampaignMode, str]] = ..., brand: _Optional[_Union[BrandContext, _Mapping]] = ..., door: _Optional[_Union[DoorContext, _Mapping]] = ..., city: _Optional[str] = ..., max_words: _Optional[int] = ..., evidence_ids: _Optional[_Iterable[str]] = ..., instructions: _Optional[str] = ..., attachment_id: _Optional[str] = ..., attachment_name: _Optional[str] = ...) -> None: ...

class DraftDoorPitchResponse(_message.Message):
    __slots__ = ("script", "battlecard", "recommended_sku", "mode_paragraph", "opening", "why_this_door", "pitch", "product_to_lead", "ask", "close", "sources", "attribution", "error_code", "error_message")
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    BATTLECARD_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_SKU_FIELD_NUMBER: _ClassVar[int]
    MODE_PARAGRAPH_FIELD_NUMBER: _ClassVar[int]
    OPENING_FIELD_NUMBER: _ClassVar[int]
    WHY_THIS_DOOR_FIELD_NUMBER: _ClassVar[int]
    PITCH_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_TO_LEAD_FIELD_NUMBER: _ClassVar[int]
    ASK_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    script: str
    battlecard: Battlecard
    recommended_sku: Sku
    mode_paragraph: str
    opening: str
    why_this_door: str
    pitch: str
    product_to_lead: str
    ask: str
    close: str
    sources: _containers.RepeatedCompositeFieldContainer[Citation]
    attribution: ModelAttribution
    error_code: _common_pb2.ErrorCode
    error_message: str
    def __init__(self, script: _Optional[str] = ..., battlecard: _Optional[_Union[Battlecard, _Mapping]] = ..., recommended_sku: _Optional[_Union[Sku, _Mapping]] = ..., mode_paragraph: _Optional[str] = ..., opening: _Optional[str] = ..., why_this_door: _Optional[str] = ..., pitch: _Optional[str] = ..., product_to_lead: _Optional[str] = ..., ask: _Optional[str] = ..., close: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[Citation, _Mapping]]] = ..., attribution: _Optional[_Union[ModelAttribution, _Mapping]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class LlmOnlyBaselineRequest(_message.Message):
    __slots__ = ("meta", "brand", "city", "mode", "max_words")
    META_FIELD_NUMBER: _ClassVar[int]
    BRAND_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    MAX_WORDS_FIELD_NUMBER: _ClassVar[int]
    meta: _common_pb2.RequestMeta
    brand: BrandContext
    city: str
    mode: CampaignMode
    max_words: int
    def __init__(self, meta: _Optional[_Union[_common_pb2.RequestMeta, _Mapping]] = ..., brand: _Optional[_Union[BrandContext, _Mapping]] = ..., city: _Optional[str] = ..., mode: _Optional[_Union[CampaignMode, str]] = ..., max_words: _Optional[int] = ...) -> None: ...

class LlmOnlyBaselineResponse(_message.Message):
    __slots__ = ("text", "venue_names", "attribution", "error_code", "error_message")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    VENUE_NAMES_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    text: str
    venue_names: _containers.RepeatedScalarFieldContainer[str]
    attribution: ModelAttribution
    error_code: _common_pb2.ErrorCode
    error_message: str
    def __init__(self, text: _Optional[str] = ..., venue_names: _Optional[_Iterable[str]] = ..., attribution: _Optional[_Union[ModelAttribution, _Mapping]] = ..., error_code: _Optional[_Union[_common_pb2.ErrorCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...
