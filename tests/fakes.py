"""Fakes shared by the tests. Nothing here touches the network."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from bothsides.matching.types import MatcherError, MatchResult, MatchSource, Tri


@dataclass
class ManualClock:
    """A clock that moves only when a test moves it."""

    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current = self.current + timedelta(**kwargs)


@dataclass
class FakeInteraction:
    output_text: str | None
    status: str = "completed"


class FakeInteractions:
    """Stands in for ``client.interactions``."""

    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        reply = self.reply(kwargs) if callable(self.reply) else self.reply
        if isinstance(reply, BaseException):
            raise reply
        return reply


@dataclass
class FakeModel:
    name: str
    supported_actions: list[str] | None = field(default_factory=lambda: ["generateContent"])


class FakeModels:
    def __init__(self, names: list[str] | BaseException) -> None:
        self.names = names

    def list(self) -> list[FakeModel]:
        if isinstance(self.names, BaseException):
            raise self.names
        return [FakeModel(f"models/{name}") for name in self.names]


class FakeGeminiClient:
    """Stands in for ``genai.Client``."""

    def __init__(self, reply: Any = None, models: list[str] | BaseException | None = None) -> None:
        self.interactions = FakeInteractions(reply)
        self.models = FakeModels(models if models is not None else ["gemini-3.8-flash"])


def gemini_json(
    probability: Any = 0.93, same_relation: Any = "true", same_reason: Any = "true", note: Any = "Both name rent."
) -> str:
    return json.dumps(
        {
            "probability": probability,
            "same_relation": same_relation,
            "same_reason": same_reason,
            "note": note,
        }
    )


def gemini_reply(**kwargs: Any) -> FakeInteraction:
    return FakeInteraction(gemini_json(**kwargs))


class StubMatcher:
    """Returns a fixed result, or raises, and records what it was asked."""

    def __init__(self, result: MatchResult | BaseException) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        self.calls.append((receiver_text, sender_text))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def gemini_result(
    probability: float = 0.93, same_reason: Tri = Tri.TRUE, same_relation: Tri = Tri.TRUE
) -> MatchResult:
    return MatchResult(
        probability=probability,
        same_relation=same_relation,
        same_reason=same_reason,
        note="Fake model note.",
        source=MatchSource.GEMINI,
        model="gemini-fake",
    )


class BlockingMatcher:
    """Waits until the test lets it go."""

    def __init__(self, result: MatchResult) -> None:
        self.result = result
        self.started = threading.Event()
        self.release = threading.Event()

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        self.started.set()
        self.release.wait(timeout=10)
        return self.result


class InlineExecutor:
    """Runs background work at once. Like a thread, it keeps errors to itself."""

    def __init__(self) -> None:
        self.errors: list[Exception] = []

    def submit(self, work: Callable[[], None]) -> None:
        try:
            work()
        except Exception as error:
            self.errors.append(error)


__all__ = [
    "BlockingMatcher",
    "FakeGeminiClient",
    "FakeInteraction",
    "InlineExecutor",
    "ManualClock",
    "MatcherError",
    "StubMatcher",
    "gemini_json",
    "gemini_reply",
    "gemini_result",
]
