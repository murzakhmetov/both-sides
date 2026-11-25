"""How often a public page may ask the language model."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from .. import config
from ..clock import Clock
from .ratelimit import RateLimiter


class Budget:
    """A share for every visitor, and a limit a minute and a day for one running copy.

    Only a limit set at Google covers all running copies together.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._share = RateLimiter(config.ONLINE_GEMINI_SHARE, config.RATE_WINDOW)
        self._minute = RateLimiter(config.ONLINE_GEMINI_CALLS, config.RATE_WINDOW)
        self._day = RateLimiter(config.ONLINE_GEMINI_CALLS_A_DAY, timedelta(days=1))
        self._here = threading.local()

    @contextmanager
    def of(self, visitor: str) -> Iterator[None]:
        """What this thread asks inside belongs to *visitor*."""
        self._here.visitor = visitor
        try:
            yield
        finally:
            self._here.visitor = ""

    def may_ask(self) -> bool:
        """Count one request to the model, unless it is one too many."""
        now = self._clock.now()
        visitor = getattr(self._here, "visitor", "")
        limits = ((self._share, visitor), (self._minute, "all"), (self._day, "all"))
        return all(limiter.wait_seconds(key, now) == 0 for limiter, key in limits)
