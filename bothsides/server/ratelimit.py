"""A sliding-window rate limit per client address."""

from __future__ import annotations

import math
import threading
from collections import deque
from datetime import datetime, timedelta

_MAX_KEYS = 10_000


class RateLimiter:
    """Allows ``limit`` requests per ``window`` for each key."""

    def __init__(self, limit: int, window: timedelta) -> None:
        self._limit = limit
        self._window = window
        self._hits: dict[str, deque[datetime]] = {}
        self._lock = threading.Lock()

    def wait_seconds(self, key: str, now: datetime) -> int:
        """Count one request. Returns 0, or the seconds to wait when it is refused."""
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._forget_idle(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(1, math.ceil((self._window - (now - hits[0])).total_seconds()))
            hits.append(now)
            return 0

    def _forget_idle(self, now: datetime) -> None:
        self._hits = {
            key: hits for key, hits in self._hits.items() if hits and now - hits[-1] < self._window
        }
