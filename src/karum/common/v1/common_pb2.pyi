from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EvidenceSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVIDENCE_SOURCE_UNSPECIFIED: _ClassVar[EvidenceSource]
    EVIDENCE_SOURCE_QLOO: _ClassVar[EvidenceSource]
    EVIDENCE_SOURCE_GOOGLE: _ClassVar[EvidenceSource]
    EVIDENCE_SOURCE_VERTEX: _ClassVar[EvidenceSource]
    EVIDENCE_SOURCE_KARUM: _ClassVar[EvidenceSource]

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_CODE_UNSPECIFIED: _ClassVar[ErrorCode]
    ERROR_CODE_UNRESOLVED: _ClassVar[ErrorCode]
    ERROR_CODE_EMPTY: _ClassVar[ErrorCode]
    ERROR_CODE_RATE_LIMITED: _ClassVar[ErrorCode]
    ERROR_CODE_UPSTREAM: _ClassVar[ErrorCode]
    ERROR_CODE_VALIDATION: _ClassVar[ErrorCode]
EVIDENCE_SOURCE_UNSPECIFIED: EvidenceSource
EVIDENCE_SOURCE_QLOO: EvidenceSource
EVIDENCE_SOURCE_GOOGLE: EvidenceSource
EVIDENCE_SOURCE_VERTEX: EvidenceSource
EVIDENCE_SOURCE_KARUM: EvidenceSource
ERROR_CODE_UNSPECIFIED: ErrorCode
ERROR_CODE_UNRESOLVED: ErrorCode
ERROR_CODE_EMPTY: ErrorCode
ERROR_CODE_RATE_LIMITED: ErrorCode
ERROR_CODE_UPSTREAM: ErrorCode
ERROR_CODE_VALIDATION: ErrorCode

class GeoPoint(_message.Message):
    __slots__ = ("latitude", "longitude")
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    latitude: float
    longitude: float
    def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ...) -> None: ...

class PlaceFacts(_message.Message):
    __slots__ = ("address", "website", "phone", "hours", "is_closed", "location")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WEBSITE_FIELD_NUMBER: _ClassVar[int]
    PHONE_FIELD_NUMBER: _ClassVar[int]
    HOURS_FIELD_NUMBER: _ClassVar[int]
    IS_CLOSED_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    address: str
    website: str
    phone: str
    hours: str
    is_closed: bool
    location: GeoPoint
    def __init__(self, address: _Optional[str] = ..., website: _Optional[str] = ..., phone: _Optional[str] = ..., hours: _Optional[str] = ..., is_closed: _Optional[bool] = ..., location: _Optional[_Union[GeoPoint, _Mapping]] = ...) -> None: ...

class EntityRef(_message.Message):
    __slots__ = ("id", "type", "name", "city", "place")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    PLACE_FIELD_NUMBER: _ClassVar[int]
    id: str
    type: str
    name: str
    city: str
    place: PlaceFacts
    def __init__(self, id: _Optional[str] = ..., type: _Optional[str] = ..., name: _Optional[str] = ..., city: _Optional[str] = ..., place: _Optional[_Union[PlaceFacts, _Mapping]] = ...) -> None: ...

class Tag(_message.Message):
    __slots__ = ("urn", "label", "type", "score")
    URN_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    urn: str
    label: str
    type: str
    score: float
    def __init__(self, urn: _Optional[str] = ..., label: _Optional[str] = ..., type: _Optional[str] = ..., score: _Optional[float] = ...) -> None: ...

class SubScore(_message.Message):
    __slots__ = ("name", "value", "raw_value", "inputs", "source")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    RAW_VALUE_FIELD_NUMBER: _ClassVar[int]
    INPUTS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: float
    raw_value: float
    inputs: _containers.RepeatedScalarFieldContainer[str]
    source: EvidenceSource
    def __init__(self, name: _Optional[str] = ..., value: _Optional[float] = ..., raw_value: _Optional[float] = ..., inputs: _Optional[_Iterable[str]] = ..., source: _Optional[_Union[EvidenceSource, str]] = ...) -> None: ...

class EvidenceCall(_message.Message):
    __slots__ = ("id", "source", "endpoint", "parameters", "result_count", "latency_ms", "error_code", "error_message")
    ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    RESULT_COUNT_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    id: str
    source: EvidenceSource
    endpoint: str
    parameters: str
    result_count: int
    latency_ms: int
    error_code: ErrorCode
    error_message: str
    def __init__(self, id: _Optional[str] = ..., source: _Optional[_Union[EvidenceSource, str]] = ..., endpoint: _Optional[str] = ..., parameters: _Optional[str] = ..., result_count: _Optional[int] = ..., latency_ms: _Optional[int] = ..., error_code: _Optional[_Union[ErrorCode, str]] = ..., error_message: _Optional[str] = ...) -> None: ...

class RequestMeta(_message.Message):
    __slots__ = ("trace_id", "job_id")
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    trace_id: str
    job_id: str
    def __init__(self, trace_id: _Optional[str] = ..., job_id: _Optional[str] = ...) -> None: ...
