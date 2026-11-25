"""Immutable case data. Every change makes a new object."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from ..decision.facts import BankFacts
from ..decision.reasons import ReasonCode
from ..decision.stories import Story
from ..matching.types import MatchResult


class Side(str, Enum):
    """The two people around one transfer."""

    RECEIVER = "receiver"
    SENDER = "sender"


class Actor(str, Enum):
    """Who did a step of the decision trail."""

    SYSTEM = "system"
    RECEIVER = "receiver"
    SENDER = "sender"
    STAFF = "staff"


class CaseState(str, Enum):
    """Where a stopped transfer is."""

    AWAITING_RECEIVER = "awaiting_receiver"
    AWAITING_SENDER = "awaiting_sender"
    COMPARING = "comparing"
    CREDITED = "credited"
    WITH_SPECIALIST = "with_specialist"
    HELD = "held"
    RETURNED = "returned"


#: States that only a person can end.
STAFF_STATES = frozenset({CaseState.WITH_SPECIALIST, CaseState.HELD})
#: States with an answer deadline.
ASKING_STATES = frozenset({CaseState.AWAITING_RECEIVER, CaseState.AWAITING_SENDER})


@dataclass(frozen=True, slots=True)
class Person:
    """An invented bank client. Only the first name is ever shown to the other side."""

    id: str
    name_ru: str
    name_kk: str
    name_en: str


@dataclass(frozen=True, slots=True)
class Transfer:
    """The stopped transfer. The message is written by the sender."""

    sender: Person
    receiver: Person
    amount: int
    message: str


@dataclass(frozen=True, slots=True)
class Answer:
    """What one person told the bank, and when."""

    text: str
    at: datetime


@dataclass(frozen=True, slots=True)
class Objection:
    """A client disagrees with a hold."""

    side: Side
    at: datetime


@dataclass(frozen=True, slots=True)
class TrailEntry:
    """One line of the decision trail."""

    at: datetime
    actor: Actor
    event: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Case:
    """One stopped transfer with everything that happened to it."""

    id: str
    scene: str | None
    transfer: Transfer
    facts: BankFacts
    state: CaseState
    stopped_at: datetime
    answer_by: datetime
    deadline_at: datetime
    trail: tuple[TrailEntry, ...]
    receiver_answer: Answer | None = None
    sender_answer: Answer | None = None
    comparing_since: datetime | None = None
    match: MatchResult | None = None
    similar_receivers: int = 0
    reasons: tuple[ReasonCode, ...] = ()
    decided_at: datetime | None = None
    denied_at: datetime | None = None
    deny_first_tap_at: datetime | None = None
    #: The sender is asked although the receiver's denial has already decided.
    sender_asked_late: bool = False
    closed_at: datetime | None = None
    objections: tuple[Objection, ...] = ()


@dataclass(frozen=True, slots=True)
class Board:
    """All cases of the running demo."""

    cases: tuple[Case, ...]
    active_id: str
    stories: tuple[Story, ...]
    next_number: int

    def find(self, case_id: str) -> Case | None:
        """Return the case with this number, or None."""
        return next((case for case in self.cases if case.id == case_id), None)

    @property
    def active(self) -> Case:
        """The case both phones and the stage show."""
        found = self.find(self.active_id)
        if found is None:
            raise LookupError("the board has no active case")
        return found

    def with_case(self, case: Case) -> "Board":
        """Return a board where this case replaces the one with the same number."""
        cases = tuple(case if item.id == case.id else item for item in self.cases)
        return replace(self, cases=cases)

    def with_story(self, story: Story) -> "Board":
        """Return a board that also remembers this sender story."""
        return replace(self, stories=(*self.stories, story))
