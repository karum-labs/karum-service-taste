"""Rate-limit accounting and pacing for Qloo calls (PLAN.md §7).

Qloo publishes its budgets on every response — ``X-Second-RateLimit-*`` and
``X-Month-RateLimit-*`` (observed 5/second and 10,000/month on the hackathon
key, 18 Oct 2026). The client stays under the per-second budget with a
minimum-interval :class:`Pacer`, holds off when a response exhausts it, and
reads the month budget before spending calls blindly — the fixture pass left a
month window that turns over mid-November, inside judging, so prewarm reads
``X-Month-RateLimit-Reset`` first (PLAN.md §13).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping

from pydantic import BaseModel, ConfigDict


class RateLimitSnapshot(BaseModel):
    """One response's rate-limit headers, parsed to numbers."""

    model_config = ConfigDict(frozen=True)

    second_limit: float | None = None
    second_remaining: float | None = None
    second_reset: float | None = None
    month_limit: float | None = None
    month_remaining: float | None = None
    month_reset: float | None = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> RateLimitSnapshot | None:
        """Parse the ``X-{Second,Month}-RateLimit-*`` headers; ``None`` if absent."""
        lowered = {key.lower(): value for key, value in headers.items()}

        def number(name: str) -> float | None:
            raw = lowered.get(name)
            if raw is None:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        snapshot = cls(
            second_limit=number("x-second-ratelimit-limit"),
            second_remaining=number("x-second-ratelimit-remaining"),
            second_reset=number("x-second-ratelimit-reset"),
            month_limit=number("x-month-ratelimit-limit"),
            month_remaining=number("x-month-ratelimit-remaining"),
            month_reset=number("x-month-ratelimit-reset"),
        )
        if all(value is None for value in snapshot.model_dump().values()):
            return None
        return snapshot


class Pacer:
    """Serialize calls to a minimum interval, with header-driven holds.

    ``clock`` and ``sleep`` are injectable so tests run without wall time.
    """

    def __init__(
        self,
        min_interval: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min_interval = max(0.0, min_interval)
        self._clock = clock
        self._sleep = sleep
        self._next_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def min_interval(self) -> float:
        """The configured spacing between calls, in seconds."""
        return self._min_interval

    async def wait(self) -> None:
        """Block until this caller may issue a call, then claim the slot."""
        async with self._lock:
            now = self._clock()
            delay = self._next_at - now
            if delay > 0:
                await self._sleep(delay)
                now = self._clock()
            self._next_at = now + self._min_interval

    async def hold(self, seconds: float) -> None:
        """Refuse calls for at least ``seconds`` from now."""
        if seconds <= 0:
            return
        async with self._lock:
            self._next_at = max(self._next_at, self._clock() + seconds)
