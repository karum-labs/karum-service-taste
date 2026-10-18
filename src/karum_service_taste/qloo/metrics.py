"""In-process call metrics for the Qloo client (PLAN.md §7).

Per-endpoint call counts, failure counts by taxonomy bucket, row totals, and
latency aggregates, exposed as a snapshot for health reporting. Deliberately
dependency-free: the judging window needs numbers, not a Prometheus pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from karum_service_taste.qloo.errors import ErrorCode


@dataclass
class EndpointMetrics:
    """Aggregates for one endpoint such as ``insights.place``."""

    calls: int = 0
    errors: int = 0
    rows: int = 0
    error_codes: dict[str, int] = field(default_factory=dict)
    latency_ms_total: float = 0.0
    latency_ms_max: float = 0.0

    @property
    def latency_ms_avg(self) -> float:
        """Mean call latency; zero before the first call."""
        return self.latency_ms_total / self.calls if self.calls else 0.0


class QlooMetrics:
    """A tiny registry the client updates after every logical call."""

    def __init__(self) -> None:
        self._endpoints: dict[str, EndpointMetrics] = {}

    def record_call(self, endpoint: str, *, duration_ms: float, rows: int = 0) -> None:
        """Record one completed logical call (success or failure)."""
        metrics = self._endpoints.setdefault(endpoint, EndpointMetrics())
        metrics.calls += 1
        metrics.rows += rows
        metrics.latency_ms_total += duration_ms
        metrics.latency_ms_max = max(metrics.latency_ms_max, duration_ms)

    def record_error(self, endpoint: str, code: ErrorCode | str) -> None:
        """Record one failed call under its taxonomy bucket."""
        metrics = self._endpoints.setdefault(endpoint, EndpointMetrics())
        metrics.errors += 1
        key = code.value if isinstance(code, ErrorCode) else str(code)
        metrics.error_codes[key] = metrics.error_codes.get(key, 0) + 1

    def snapshot(self) -> dict[str, dict[str, object]]:
        """A JSON-ready view for health reporting and tests."""
        return {
            endpoint: {
                "calls": metrics.calls,
                "errors": metrics.errors,
                "rows": metrics.rows,
                "error_codes": dict(metrics.error_codes),
                "latency_ms_avg": round(metrics.latency_ms_avg, 3),
                "latency_ms_max": round(metrics.latency_ms_max, 3),
            }
            for endpoint, metrics in sorted(self._endpoints.items())
        }
