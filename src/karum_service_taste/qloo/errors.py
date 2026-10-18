"""Typed failures for the Qloo client (PLAN.md §7).

Each error maps onto the shared taxonomy in ``karum/common/v1/common.proto``;
:class:`ErrorCode` mirrors the proto enum so this layer never imports
generated protobufs. The gRPC servicers convert :class:`ErrorCode` to the proto
enum (``proto_name`` renders the wire spelling).

The client raises these for *transport-level* outcomes. A 200 that contains no
rows is not an error here: misses arrive as empty ``rows`` plus ``warnings``,
and the service layer decides whether a miss is ``ERROR_CODE_UNRESOLVED`` or
``ERROR_CODE_EMPTY`` (PLAN.md §8, §14).
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Mirror of ``karum.common.v1.ErrorCode`` with the proto prefix off."""

    UNSPECIFIED = "unspecified"
    UNRESOLVED = "unresolved"
    EMPTY = "empty"
    RATE_LIMITED = "rate_limited"
    UPSTREAM = "upstream"
    VALIDATION = "validation"

    @property
    def proto_name(self) -> str:
        """The proto enum value, e.g. ``ERROR_CODE_RATE_LIMITED``."""
        return f"ERROR_CODE_{self.value.upper()}"


class QlooError(Exception):
    """Base class for every failure raised by the Qloo client.

    Attributes:
        error_code: the shared taxonomy bucket for the failure.
        detail: operator-readable, redaction-safe description.
        status: the HTTP status when one was received, else ``None``.
        endpoint: the client endpoint label, e.g. ``insights.place``.
        retry_after: seconds the upstream asked us to wait, when it said so.
    """

    error_code: ErrorCode = ErrorCode.UPSTREAM
    #: Whether the caller may sensibly retry the same call later. The client
    #: has already exhausted its own retries by the time this is raised;
    #: callers such as the prewarm job use this to decide on a second pass.
    retryable: bool = False

    def __init__(
        self,
        detail: str,
        *,
        status: int | None = None,
        endpoint: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.detail = detail
        self.status = status
        self.endpoint = endpoint
        self.retry_after = retry_after
        super().__init__(detail)


class QlooValidationError(QlooError):
    """The request itself was unusable; nothing was sent upstream."""

    error_code = ErrorCode.VALIDATION
    retryable = False


class QlooRateLimitedError(QlooError):
    """The upstream (or the month budget) refused the call for rate."""

    error_code = ErrorCode.RATE_LIMITED
    retryable = True


class QlooUpstreamError(QlooError):
    """The upstream returned an unexpected failure."""

    error_code = ErrorCode.UPSTREAM
    retryable = True


class QlooTransportError(QlooUpstreamError):
    """No response arrived: timeout, DNS failure, connection reset."""


class QlooPayloadError(QlooUpstreamError):
    """A success status carried a payload Karum cannot read.

    Retrying is pointless — the upstream already answered; the problem is the
    answer (or this client's model of it), so the error is not retryable.
    """

    retryable = False


class QlooFixtureError(QlooValidationError):
    """The fixture pack is missing, malformed, or inconsistent."""


class QlooFixtureMissError(QlooFixtureError):
    """Fixture mode was asked for a request the pack does not record.

    This is deliberate strictness (PLAN.md §4): fixture mode serves *exactly*
    the locked recordings, so a request that does not match one is a bug, not
    something to paper over with a synthetic answer.
    """


def error_for_status(
    status: int,
    detail: str,
    *,
    endpoint: str,
    retry_after: float | None = None,
) -> QlooError:
    """Map an HTTP failure status onto the shared taxonomy (PLAN.md §7)."""
    if status == 429:
        return QlooRateLimitedError(
            detail, status=status, endpoint=endpoint, retry_after=retry_after
        )
    # 4xx other than 429 means the request (or its credentials) is the
    # problem; auth failures (401/403) and missing resources are upstream
    # conditions the caller cannot fix by editing the request.
    if 400 <= status < 500 and status not in (401, 403, 404):
        return QlooValidationError(detail, status=status, endpoint=endpoint)
    return QlooUpstreamError(detail, status=status, endpoint=endpoint)


def is_retryable_status(status: int) -> bool:
    """Whether a failed call status is worth another attempt."""
    return status == 429 or status >= 500
