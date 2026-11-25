"""Pure steps of the workflow: a case goes in, a new case comes out."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .. import config
from ..decision.facts import BankFacts, risky_facts
from ..decision.gate import GateInput, Outcome, decide
from ..decision.reasons import ReasonCode
from ..matching.denials import DenialKind, find_denial
from ..matching.types import MatchResult
from .deadlines import hold_deadline
from .errors import wrong_step
from .model import (
    ASKING_STATES,
    STAFF_STATES,
    Actor,
    Answer,
    Case,
    CaseState,
    Objection,
    Side,
    TrailEntry,
    Transfer,
)

_TYPED_REASONS = {
    DenialKind.DENIAL: ReasonCode.DENIAL_IN_TEXT,
    DenialKind.COACHED: ReasonCode.COACHED_IN_TEXT,
}


def _log(case: Case, at: datetime, actor: Actor, event: str, *details: str) -> Case:
    return replace(case, trail=(*case.trail, TrailEntry(at, actor, event, details)))


def _require(case: Case, *states: CaseState) -> None:
    if case.state not in states:
        raise wrong_step()


def open_case(
    case_id: str, scene: str | None, transfer: Transfer, facts: BankFacts, now: datetime
) -> Case:
    """Start from a transfer that the bank's anti-fraud has already stopped."""
    trail = (
        TrailEntry(now, Actor.SYSTEM, "transfer_stopped"),
        TrailEntry(now, Actor.SYSTEM, "receiver_asked"),
    )
    return Case(
        id=case_id,
        scene=scene,
        transfer=transfer,
        facts=facts,
        state=CaseState.AWAITING_RECEIVER,
        stopped_at=now,
        answer_by=now + config.ANSWER_WINDOW,
        deadline_at=hold_deadline(now),
        trail=trail,
    )


def _to_person(case: Case, reasons: tuple[ReasonCode, ...], now: datetime) -> Case:
    moved = replace(case, state=CaseState.WITH_SPECIALIST, reasons=reasons, decided_at=now)
    return _log(moved, now, Actor.SYSTEM, "decided_person", *(reason.value for reason in reasons))


def _ask_sender_late(case: Case, now: datetime) -> Case:
    """Ask the sender as usual after a denial: for the case file, and so that
    the sender's phone does not tell a denial from any other review."""
    asked = replace(case, sender_asked_late=True, answer_by=now + config.ANSWER_WINDOW)
    return _log(asked, now, Actor.SYSTEM, "sender_asked")


def is_sender_asked_late(case: Case, now: datetime) -> bool:
    """True while the sender may still answer a case that a person already has."""
    return (
        case.state is CaseState.WITH_SPECIALIST
        and case.sender_asked_late
        and case.sender_answer is None
        and now < case.answer_by
    )


def submit_receiver_answer(case: Case, text: str, now: datetime) -> Case:
    """The receiver answers first; then the sender is asked."""
    _require(case, CaseState.AWAITING_RECEIVER)
    answered = _log(
        replace(case, receiver_answer=Answer(text, now), deny_first_tap_at=None),
        now,
        Actor.RECEIVER,
        "receiver_answered",
    )
    denial = find_denial(text)
    if denial:
        return _ask_sender_late(_to_person(answered, (_TYPED_REASONS[denial],), now), now)
    asked = replace(answered, state=CaseState.AWAITING_SENDER, answer_by=now + config.ANSWER_WINDOW)
    return _log(asked, now, Actor.SYSTEM, "sender_asked")


def _keep_late_answer(case: Case, text: str, now: datetime) -> Case:
    """Store the answer for the specialist. Nothing is compared."""
    denial = find_denial(text)
    found = (_TYPED_REASONS[denial],) if denial else ()
    reasons = tuple(dict.fromkeys((*case.reasons, *found)))
    kept = replace(case, sender_answer=Answer(text, now), reasons=reasons)
    return _log(kept, now, Actor.SENDER, "sender_answered", *(reason.value for reason in found))


def submit_sender_answer(case: Case, text: str, now: datetime) -> Case:
    """The sender answers second; then both answers are compared."""
    if is_sender_asked_late(case, now):
        return _keep_late_answer(case, text, now)
    _require(case, CaseState.AWAITING_SENDER)
    answered = _log(
        replace(case, sender_answer=Answer(text, now)), now, Actor.SENDER, "sender_answered"
    )
    denial = find_denial(text)
    if denial:
        return _to_person(answered, (_TYPED_REASONS[denial],), now)
    return replace(answered, state=CaseState.COMPARING, comparing_since=now)


def note_similar(case: Case, similar: int) -> Case:
    """Keep the number of similar stories for the file, also when nothing is compared."""
    return replace(case, similar_receivers=similar)


def apply_comparison(case: Case, match: MatchResult | None, similar: int, now: datetime) -> Case:
    """Put the matcher's result through the release gate."""
    _require(case, CaseState.COMPARING)
    if case.receiver_answer is None or case.sender_answer is None:
        raise wrong_step()
    decision = decide(
        GateInput(
            match=match,
            receiver_text=case.receiver_answer.text,
            sender_text=case.sender_answer.text,
            risky_facts=len(risky_facts(case.facts)),
            similar_receivers=similar,
        )
    )
    details = (match.source.value, f"{match.shown_probability:.4f}") if match else ("none",)
    compared = _log(
        replace(case, match=match, similar_receivers=similar), now, Actor.SYSTEM, "compared", *details
    )
    if decision.outcome is Outcome.PERSON:
        return _to_person(compared, decision.reasons, now)
    if decision.outcome is Outcome.HOLD:
        held = replace(compared, state=CaseState.HELD, reasons=decision.reasons, decided_at=now)
        return _log(held, now, Actor.SYSTEM, "decided_hold", *(r.value for r in decision.reasons))
    credited = replace(compared, state=CaseState.CREDITED, decided_at=now, closed_at=now)
    return _log(credited, now, Actor.SYSTEM, "decided_release")


def is_deny_armed(case: Case, now: datetime) -> bool:
    """True while a second tap would confirm "I do not know this person"."""
    first = case.deny_first_tap_at
    return first is not None and now - first <= config.DENY_CONFIRM_WINDOW


def tap_deny(case: Case, now: datetime) -> Case:
    """First tap arms the button, a second tap in time confirms."""
    _require(case, CaseState.AWAITING_RECEIVER)
    if not is_deny_armed(case, now):
        return replace(case, deny_first_tap_at=now)
    denied = replace(case, denied_at=now, deny_first_tap_at=None)
    logged = _log(denied, now, Actor.RECEIVER, "receiver_denied")
    moved = _to_person(logged, (ReasonCode.RECEIVER_DENIED,), now)
    return _ask_sender_late(_log(moved, now, Actor.SYSTEM, "return_offered"), now)


def accept_return(case: Case, now: datetime) -> Case:
    """The receiver accepts the bank's offer to return the money."""
    _require(case, CaseState.WITH_SPECIALIST)
    if case.denied_at is None:
        raise wrong_step()
    returned = replace(case, state=CaseState.RETURNED, closed_at=now)
    return _log(returned, now, Actor.RECEIVER, "return_accepted")


def expire(case: Case, now: datetime) -> Case:
    """Pass the case to a person when somebody or the matcher did not answer."""
    if case.state in ASKING_STATES and now >= case.answer_by:
        # Dated at the deadline, also when nobody looked for days.
        return _to_person(case, (ReasonCode.NO_ANSWER,), case.answer_by)
    since = case.comparing_since
    if case.state is CaseState.COMPARING and since and now - since >= config.COMPARING_TIMEOUT:
        return _to_person(case, (ReasonCode.MATCHER_UNAVAILABLE,), now)
    return case


def object_to_hold(case: Case, side: Side, now: datetime) -> Case:
    """Record one objection per side. It never ends the hold by itself."""
    _require(case, CaseState.HELD)
    if any(objection.side is side for objection in case.objections):
        return case
    noted = replace(case, objections=(*case.objections, Objection(side, now)))
    return _log(noted, now, Actor(side.value), "objection")


def close_by_staff(case: Case, state: CaseState, now: datetime) -> Case:
    """A person releases or returns the money."""
    _require(case, *STAFF_STATES)
    closed = replace(case, state=state, closed_at=now)
    event = "staff_release" if state is CaseState.CREDITED else "staff_return"
    return _log(closed, now, Actor.STAFF, event)


def is_overdue(case: Case, now: datetime) -> bool:
    """True for an open case after the fifth working day."""
    return case.state in STAFF_STATES and now > case.deadline_at
