"""One interface for every matcher, so the workflow does not care who answered."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from typing import Protocol


class Tri(str, Enum):
    """A yes/no question that may stay open."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class MatchSource(str, Enum):
    """Who scored the pair."""

    GEMINI = "gemini"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """How likely both answers describe the same transfer."""

    probability: float
    same_relation: Tri
    same_reason: Tri
    note: str
    source: MatchSource
    #: Model that answered (language model only).
    model: str = ""
    #: Why the language model did not answer, when the offline matcher stepped in.
    fallback_code: str = ""

    def __post_init__(self) -> None:
        # The comparison is false for NaN, so NaN is rejected too.
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")

    @property
    def shown_probability(self) -> float:
        """Four digits, rounded down: a score just under a threshold must not look like it."""
        return float(Decimal(str(self.probability)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN))


class MatcherError(Exception):
    """A matcher could not answer. ``code`` is safe to show to staff."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Matcher(Protocol):
    """Anything that can score two answers."""

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        """Score the pair or raise :class:`MatcherError`."""
        ...
