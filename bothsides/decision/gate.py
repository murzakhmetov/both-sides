"""The release gate. All rules in one pure function, all numbers in config."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .. import config
from ..matching.types import MatchResult, MatchSource, Tri
from .content import has_content
from .reasons import ReasonCode


class Outcome(str, Enum):
    """What happens to the stopped transfer."""

    RELEASE = "release"
    PERSON = "person"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class GateInput:
    """Everything the decision depends on."""

    match: MatchResult | None
    receiver_text: str
    sender_text: str
    risky_facts: int
    similar_receivers: int


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome and, unless it is a release, the reasons for staff."""

    outcome: Outcome
    reasons: tuple[ReasonCode, ...] = ()


def _blockers(data: GateInput, match: MatchResult, content: bool) -> tuple[ReasonCode, ...]:
    missing_reason = (
        ReasonCode.REASON_NOT_CONFIRMED
        if match.source is MatchSource.GEMINI
        else ReasonCode.NO_SHARED_REASON
    )
    checks = (
        (ReasonCode.LOW_MATCH, match.probability < config.RELEASE_PROBABILITY),
        (ReasonCode.TOO_VAGUE, not content),
        (missing_reason, match.same_reason is not Tri.TRUE),
        (ReasonCode.RISKY_FACTS, data.risky_facts > config.MAX_RISKY_FACTS_FOR_RELEASE),
        (ReasonCode.REPEATED_STORY, data.similar_receivers >= config.REPEATED_STORY_RECEIVERS),
    )
    return tuple(code for code, present in checks if present)


def _is_clear_mismatch(match: MatchResult, content: bool) -> bool:
    """Only the language model may hold, and only when both answers say something."""
    return (
        match.source is MatchSource.GEMINI
        and match.probability < config.HOLD_PROBABILITY
        and content
        and match.same_reason is not Tri.UNKNOWN
    )


def decide(data: GateInput) -> Decision:
    """Release, hold or pass to a person. A person is the default."""
    match = data.match
    content = has_content(data.receiver_text) and has_content(data.sender_text)
    if match is None:
        reason = ReasonCode.MATCHER_UNAVAILABLE if content else ReasonCode.TOO_VAGUE
        return Decision(Outcome.PERSON, (reason,))
    blockers = _blockers(data, match, content)
    if not blockers:
        return Decision(Outcome.RELEASE)
    if _is_clear_mismatch(match, content):
        rest = tuple(code for code in blockers if code is not ReasonCode.LOW_MATCH)
        return Decision(Outcome.HOLD, (ReasonCode.CLEAR_MISMATCH, *rest))
    return Decision(Outcome.PERSON, blockers)
