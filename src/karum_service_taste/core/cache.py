"""A small in-process TTL cache with an injectable clock.

Seed resolution caches its search lookups — hits and negative lookups alike —
under a short TTL (PLAN.md §8). The full cache epic (PLAN.md §13) puts Redis
behind this interface with a single-flight lock; the taste layer needs only
the keyed-TTL behaviour today.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class TtlCache[T]:
    """Keyed TTL store.

    ``None`` means "no live entry": a cached empty list (a negative lookup)
    comes back as ``[]``, so callers can cache misses deliberately.
    """

    def __init__(
        self,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        """Return the live value for ``key``, or ``None`` when absent/expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        """Store ``value`` under ``key`` for one TTL window."""
        self._entries[key] = (self._clock() + self._ttl_seconds, value)

    def __len__(self) -> int:
        """Entries retained, expired ones included until next touched."""
        return len(self._entries)
