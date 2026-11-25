"""Seeded cases that fill the console. Invented people, amounts and scores."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..cases import transitions
from ..cases.model import Case, CaseState, Person, Side, Transfer
from ..decision.facts import BankFacts
from ..decision.stories import Story
from ..matching.types import MatchResult, MatchSource, Tri
from .scenes import Scene

#: Shown instead of a model name, so nobody takes a seeded score for a real one.
SEEDED = "seeded example"

_CALM = BankFacts(account_age_days=1_100, first_time_senders_today=0, earlier_transfers=4)
_NEW = BankFacts(account_age_days=9, first_time_senders_today=1, earlier_transfers=0)
_BUSY = BankFacts(account_age_days=60, first_time_senders_today=4, earlier_transfers=0)


def case_number(now: datetime, number: int) -> str:
    """Case numbers look like BS-2026-0007."""
    return f"BS-{now.year}-{number:04d}"


def open_scene(scene: Scene, case_id: str, now: datetime) -> Case:
    """Open a fresh case for a scene."""
    return transitions.open_case(case_id, scene.id, scene.transfer, scene.facts, now)


def _person(number: int, ru: str, kk: str, en: str) -> Person:
    return Person(f"client-{number}", ru, kk, en)


def _score(probability: float, same_reason: Tri, same_relation: Tri, note: str) -> MatchResult:
    return MatchResult(
        probability=probability,
        same_relation=same_relation,
        same_reason=same_reason,
        note=note,
        source=MatchSource.GEMINI,
        model=SEEDED,
    )


def _asked(case: Case, receiver: str, sender: str, at: datetime) -> Case:
    answered = transitions.submit_receiver_answer(case, receiver, at)
    return transitions.submit_sender_answer(answered, sender, at + timedelta(minutes=2))


def _overdue_hold(case_id: str, now: datetime) -> Case:
    """A hold from twelve days ago: the five working days are over."""
    stopped = now - timedelta(days=12)
    transfer = Transfer(
        _person(901, "Бахыт", "Бақыт", "Bakhyt"), _person(902, "Олжас", "Олжас", "Olzhas"), 310_000, "за мебель"
    )
    case = transitions.open_case(case_id, None, transfer, _NEW, stopped)
    asked = _asked(case, "продал телефон покупателю", "племяннику на билеты домой", stopped + timedelta(minutes=8))
    score = _score(0.06, Tri.FALSE, Tri.FALSE, "The reasons and the relations contradict each other.")
    held = transitions.apply_comparison(asked, score, 0, stopped + timedelta(minutes=11))
    return transitions.object_to_hold(held, Side.SENDER, stopped + timedelta(days=1))


def _no_answer(case_id: str, now: datetime) -> Case:
    """The receiver never answered, so a person looks at it."""
    stopped = now - timedelta(hours=30)
    transfer = Transfer(
        _person(903, "Айнур", "Айнұр", "Ainur"), _person(904, "Руслан", "Руслан", "Ruslan"), 75_000, ""
    )
    case = transitions.open_case(case_id, None, transfer, _CALM, stopped)
    return transitions.expire(case, case.answer_by)


def _staff_released(case_id: str, now: datetime) -> Case:
    """Vague answers; a specialist called both and released the money."""
    stopped = now - timedelta(days=2, hours=3)
    transfer = Transfer(
        _person(905, "Жанар", "Жанар", "Zhanar"), _person(906, "Серик", "Серік", "Serik"), 48_000, "спасибо"
    )
    case = transitions.open_case(case_id, None, transfer, _CALM, stopped)
    asked = _asked(case, "спасибо большое", "коллеге за обед в пятницу", stopped + timedelta(minutes=5))
    score = _score(0.41, Tri.UNKNOWN, Tri.UNKNOWN, "One answer names no reason.")
    waiting = transitions.apply_comparison(asked, score, 0, stopped + timedelta(minutes=7))
    return transitions.close_by_staff(waiting, CaseState.CREDITED, stopped + timedelta(hours=4))


def _denied_and_returned(case_id: str, now: datetime) -> Case:
    """The receiver did not know the sender and agreed to the return."""
    stopped = now - timedelta(days=3)
    transfer = Transfer(
        _person(907, "Дина", "Дина", "Dina"), _person(908, "Асхат", "Асхат", "Askhat"), 200_000, "предоплата"
    )
    case = transitions.open_case(case_id, None, transfer, _BUSY, stopped)
    tapped = transitions.tap_deny(case, stopped + timedelta(minutes=3))
    denied = transitions.tap_deny(tapped, stopped + timedelta(minutes=3, seconds=2))
    return transitions.accept_return(denied, stopped + timedelta(minutes=4))


def background_cases(now: datetime, first_number: int) -> tuple[tuple[Case, ...], tuple[Story, ...], int]:
    """Return the seeded cases, their sender stories and the next free number."""
    builders = (_overdue_hold, _denied_and_returned, _staff_released, _no_answer)
    cases = tuple(
        build(case_number(now, first_number + index), now) for index, build in enumerate(builders)
    )
    stories = tuple(
        Story(case.transfer.receiver.id, case.sender_answer.text, case.sender_answer.at, case.id)
        for case in cases
        if case.sender_answer is not None
    )
    return cases, stories, first_number + len(builders)
