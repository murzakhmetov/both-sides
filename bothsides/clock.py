"""Time source. Everything that needs "now" takes a clock, so tests can move it."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .config import BANK_TIMEZONE


class Clock(Protocol):
    """Anything that can tell the current time with a time zone."""

    def now(self) -> datetime:
        """Return the current time in the bank's time zone."""
        ...


def _bank_time() -> datetime:
    return datetime.now(BANK_TIMEZONE)


class SystemClock:
    """The real clock in the bank's time zone, but it never runs backwards.

    When the computer's clock is set back, time simply goes on: the two-tap
    window, the repeated-story check and the rate limits stay right. When it is
    set forward (also after the laptop slept), this clock follows.
    """

    def __init__(
        self, wall: Callable[[], datetime] = _bank_time, steady: Callable[[], float] = time.monotonic
    ) -> None:
        self._wall = wall
        self._steady = steady
        self._lock = threading.Lock()
        self._last = wall()
        self._last_steady = steady()

    def now(self) -> datetime:
        with self._lock:
            steady = self._steady()
            expected = self._last + timedelta(seconds=steady - self._last_steady)
            self._last = max(expected, self._wall())
            self._last_steady = steady
            return self._last
