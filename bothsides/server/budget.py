"""How often a public page may ask the language model."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from .. import config
from ..clock import Clock
from .ratelimit import RateLimiter

_DAY = timedelta(days=1)


class Budget:
    """Shares of a visitor and of an address, and limits for one running copy.

    A visitor without cookies is new every time, so the address has a share as well. Only a
    limit set at Google covers all running copies together.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._limits = (
            ("visitor", RateLimiter(config.ONLINE_GEMINI_SHARE, config.RATE_WINDOW)),
            ("address", RateLimiter(config.ONLINE_GEMINI_ADDRESS, config.RATE_WINDOW)),
            ("address", RateLimiter(config.ONLINE_GEMINI_ADDRESS_A_DAY, _DAY)),
            ("all", RateLimiter(config.ONLINE_GEMINI_CALLS, config.RATE_WINDOW)),
            ("all", RateLimiter(config.ONLINE_GEMINI_CALLS_A_DAY, _DAY)),
        )
        self._here = threading.local()

    @contextmanager
    def of(self, visitor: str, address: str) -> Iterator[None]:
        """What this thread asks inside belongs to *visitor* at *address*."""
        self._here.who = {"visitor": visitor, "address": address}
        try:
            yield
        finally:
            self._here.who = {}

    def may_ask(self) -> bool:
        """Count one request to the model, unless it is one too many."""
        now = self._clock.now()
        who = getattr(self._here, "who", {})
        return all(limiter.wait_seconds(who.get(kind, kind), now) == 0 for kind, limiter in self._limits)
