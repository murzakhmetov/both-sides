"""Phones never carry the other answer, the score, the reason or the message too early."""

from __future__ import annotations

from typing import Any

import pytest

from bothsides.decision.reasons import ReasonCode
from bothsides.matching.types import Tri

from .fakes import StubMatcher, gemini_result
from .helpers import (
    BROTHER_RECEIVER,
    BROTHER_SENDER,
    SISTER_RECEIVER,
    SISTER_SENDER,
    active_id,
    as_json,
    make_service,
)

ALLOWED_KEYS = {
    "case_id",
    "case_number",
    "side",
    "status",
    "answered",
    "other_name",
    "amount",
    "answer_by",
    "deadline_at",
    "ground",
    "objection_sent",
    "deny_armed_seconds",
    "denied",
    "message",
}
FORBIDDEN_WORDS = {code.value for code in ReasonCode} | {
    "probability",
    "same_reason",
    "same_relation",
    "gemini",
    "offline",
    "risky",
    "new_account",
    "first_time_senders",
    "similar",
    "scene",
    "note",
    "trail",
    "match",
}


def check_phone(view: dict[str, Any], hidden: list[str]) -> None:
    assert set(view) <= ALLOWED_KEYS
    text = as_json(view)
    for secret in hidden:
        assert secret not in text, (secret, text)
    for word in FORBIDDEN_WORDS:
        assert word not in text, (word, text)


def check_both(service: Any, hidden: list[str]) -> None:
    for side in ("receiver", "sender"):
        check_phone(service.phone(side), hidden)


@pytest.mark.parametrize(
    ("probability", "same_reason", "state"),
    [(0.97, Tri.TRUE, "credited"), (0.5, Tri.FALSE, "with_specialist"), (0.02, Tri.FALSE, "held")],
)
def test_no_answer_score_or_reason_on_any_phone_at_any_step(probability: float, same_reason: Tri, state: str) -> None:
    service, _ = make_service(StubMatcher(gemini_result(probability, same_reason)))
    service.start_scene("brother")
    case_id = active_id(service)
    hidden = [BROTHER_RECEIVER, BROTHER_SENDER, str(probability), "Fake model note"]
    check_both(service, hidden)
    check_phone(service.answer("receiver", case_id, BROTHER_RECEIVER), hidden)
    check_both(service, hidden)
    check_phone(service.answer("sender", case_id, BROTHER_SENDER), hidden)
    check_both(service, hidden)
    assert service.case_file(case_id)["state"] == state
    if state != "credited":
        service.close_case(case_id, "return")
        check_both(service, hidden)


def test_denial_reason_is_not_shown_to_the_sender() -> None:
    service, _ = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    check_both(service, [])
    service.answer("sender", case_id, "оплата за товар с сайта")
    check_both(service, ["оплата за товар с сайта"])
    assert service.phone("sender")["status"] == "with_specialist"


def _sender_views(receiver_step: Any) -> list[dict[str, Any]]:
    """What the sender's phone shows before, during and after the sender's answer."""
    service, _ = make_service()
    service.start_scene("sister")
    case_id = active_id(service)
    views = [service.phone("sender")]
    receiver_step(service, case_id)
    views.append(service.phone("sender"))
    views.append(service.answer("sender", case_id, SISTER_SENDER))
    return [{k: v for k, v in view.items() if k not in {"case_id", "case_number"}} for view in views]


def test_sender_sees_the_same_whatever_the_reason_of_the_review() -> None:
    def deny(service: Any, case_id: str) -> None:
        service.tap_deny(case_id)
        service.tap_deny(case_id)

    texts = (SISTER_RECEIVER, "я не знаю этого человека", "мне сказали так сказать", "спасибо большое")
    runs = [_sender_views(lambda s, c, text=text: s.answer("receiver", c, text)) for text in texts]
    runs.append(_sender_views(deny))
    assert all(run == runs[0] for run in runs)


def test_only_the_receiver_knows_about_the_own_denial() -> None:
    service, _ = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    assert service.phone("receiver")["denied"] is True
    assert "denied" not in service.phone("sender")
    service.accept_return(case_id)
    assert service.phone("receiver")["denied"] is True
    assert "denied" not in service.phone("sender")


def test_transfer_message_is_hidden_until_the_money_is_credited() -> None:
    service, _ = make_service()
    service.start_scene("brother")
    case_id = active_id(service)
    message = service.case_file(case_id)["transfer"]["message"]
    assert message
    for step in (lambda: None, lambda: service.answer("receiver", case_id, BROTHER_RECEIVER)):
        step()
        assert service.phone("receiver")["message"] is None
        assert message not in as_json(service.phone("receiver"))
    service.answer("sender", case_id, BROTHER_SENDER)
    assert service.phone("receiver")["message"] == message


def test_transfer_message_stays_hidden_when_a_person_checks() -> None:
    service, _ = make_service()
    service.start_scene("sister")
    case_id = active_id(service)
    message = service.case_file(case_id)["transfer"]["message"]
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, SISTER_SENDER)
    assert service.case_file(case_id)["state"] == "with_specialist"
    assert message not in as_json(service.phone("receiver"))


def test_phones_show_a_first_name_and_the_amount_only() -> None:
    service, _ = make_service()
    service.start_scene("brother")
    for side in ("receiver", "sender"):
        view = service.phone(side)
        assert set(view["other_name"]) == {"ru", "kk", "en"}
        for name in view["other_name"].values():
            assert name.isalpha()
        assert view["amount"] > 0


def test_hold_shows_the_general_ground_and_the_deadline_on_both_phones() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.02, Tri.FALSE, Tri.FALSE)))
    service.start_scene("sister")
    case_id = active_id(service)
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, SISTER_SENDER)
    for side in ("receiver", "sender"):
        view = service.phone(side)
        assert view["status"] == "held"
        assert view["ground"] == "25-1"
        assert view["deadline_at"].startswith("2026-12-03T18:00")
        assert view["objection_sent"] is False


def test_console_list_holds_no_answers() -> None:
    service, _ = make_service()
    service.start_scene("brother")
    case_id = active_id(service)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert BROTHER_RECEIVER not in as_json(service.cases())
