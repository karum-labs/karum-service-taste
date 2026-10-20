from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HealthCheckRequest(_message.Message):
    __slots__ = ("service",)
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    service: str
    def __init__(self, service: _Optional[str] = ...) -> None: ...

class HealthCheckResponse(_message.Message):
    __slots__ = ("status", "mode", "version")
    class ServingStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SERVING_STATUS_UNSPECIFIED: _ClassVar[HealthCheckResponse.ServingStatus]
        SERVING_STATUS_SERVING: _ClassVar[HealthCheckResponse.ServingStatus]
        SERVING_STATUS_NOT_SERVING: _ClassVar[HealthCheckResponse.ServingStatus]
        SERVING_STATUS_DEGRADED: _ClassVar[HealthCheckResponse.ServingStatus]
    SERVING_STATUS_UNSPECIFIED: HealthCheckResponse.ServingStatus
    SERVING_STATUS_SERVING: HealthCheckResponse.ServingStatus
    SERVING_STATUS_NOT_SERVING: HealthCheckResponse.ServingStatus
    SERVING_STATUS_DEGRADED: HealthCheckResponse.ServingStatus
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    status: HealthCheckResponse.ServingStatus
    mode: str
    version: str
    def __init__(self, status: _Optional[_Union[HealthCheckResponse.ServingStatus, str]] = ..., mode: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
