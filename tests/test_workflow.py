"""The order of the questions, deadlines, denial, holds and staff actions."""

from __future__ import annotations

import pytest

from bothsides.cases.errors import ServiceError
from bothsides.matching.types import MatcherError, Tri

from .fakes import BlockingMatcher, ManualClock, StubMatcher, gemini_result
from .helpers import (
    BROTHER_RECEIVER,
    BROTHER_SENDER,
    SISTER_RECEIVER,
    SISTER_SENDER,
    START,
    active_id,
    make_service,
    run_scene,
)


def error_code(call: object) -> str:
    with pytest.raises(ServiceError) as caught:
        call()  # type: ignore[operator]
    return caught.value.code


def started(scene: str = "brother", matcher: object = None):
    service, clock = make_service(matcher)
    service.start_scene(scene)
    return service, clock, active_id(service)


def held_case():
    service, clock, case_id = started("sister", StubMatcher(gemini_result(0.02, Tri.FALSE, Tri.FALSE)))
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, SISTER_SENDER)
    assert service.case_file(case_id)["state"] == "held"
    return service, clock, case_id


# -- order ------------------------------------------------------------------


def test_receiver_is_asked_first() -> None:
    service, _, case_id = started()
    assert service.phone("receiver")["status"] == "question"
    assert service.phone("sender")["status"] == "waiting"
    assert error_code(lambda: service.answer("sender", case_id, BROTHER_SENDER)) == "wrong_step"
    assert service.case_file(case_id)["state"] == "awaiting_receiver"
    assert service.case_file(case_id)["sender_answer"] is None


def test_sender_is_asked_after_the_receiver() -> None:
    service, _, case_id = started()
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert service.phone("receiver")["status"] == "waiting"
    assert service.phone("sender")["status"] == "question"


def test_each_phone_knows_only_its_own_answer() -> None:
    service, _, case_id = started()
    assert [service.phone(side)["answered"] for side in ("receiver", "sender")] == [False, False]
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert [service.phone(side)["answered"] for side in ("receiver", "sender")] == [True, False]
    service.answer("sender", case_id, BROTHER_SENDER)
    assert [service.phone(side)["answered"] for side in ("receiver", "sender")] == [True, True]


def test_nobody_answers_twice() -> None:
    service, _, case_id = started()
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert error_code(lambda: service.answer("receiver", case_id, "другой ответ здесь")) == "wrong_step"
    service.answer("sender", case_id, BROTHER_SENDER)
    assert error_code(lambda: service.answer("sender", case_id, "другой ответ здесь")) == "wrong_step"


def test_matcher_gets_both_answers_in_order() -> None:
    matcher = StubMatcher(gemini_result(0.95))
    service, _, case_id = started(matcher=matcher)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert matcher.calls == []
    service.answer("sender", case_id, BROTHER_SENDER)
    assert matcher.calls == [(BROTHER_RECEIVER, BROTHER_SENDER)]


def test_released_right_after_the_second_answer() -> None:
    service, clock, case_id = started()
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    clock.advance(seconds=12.5)
    service.answer("sender", case_id, BROTHER_SENDER)
    assert service.case_file(case_id)["state"] == "credited"
    assert service.stage()["seconds"] == pytest.approx(12.5)
    assert service.phone("receiver")["status"] == "credited"
    assert service.phone("sender")["status"] == "credited"


def test_phones_show_waiting_while_the_matcher_works() -> None:
    from bothsides.cases.service import ThreadExecutor

    matcher = BlockingMatcher(gemini_result(0.95))
    service, _ = make_service(matcher, executor=ThreadExecutor())
    service.start_scene("brother")
    case_id = active_id(service)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    service.answer("sender", case_id, BROTHER_SENDER)
    assert matcher.started.wait(timeout=5)
    assert service.phone("receiver")["status"] == "waiting"
    assert service.phone("sender")["status"] == "waiting"
    assert service.stage()["case"]["state"] == "comparing"
    matcher.release.set()
    for _ in range(200):
        if service.case_file(case_id)["state"] == "credited":
            break
        import time

        time.sleep(0.01)
    assert service.case_file(case_id)["state"] == "credited"


# -- input ------------------------------------------------------------------


@pytest.mark.parametrize(("text", "code"), [("", "empty_answer"), ("   ", "empty_answer"), ("​​", "empty_answer"), ("a", "empty_answer"), ("x" * 301, "too_long")])
def test_answer_limits(text: str, code: str) -> None:
    service, _, case_id = started()
    assert error_code(lambda: service.answer("receiver", case_id, text)) == code
    assert service.phone("receiver")["status"] == "question"


def test_stale_case_number_is_refused() -> None:
    service, _, case_id = started()
    service.start_scene("brother")
    assert error_code(lambda: service.answer("receiver", case_id, BROTHER_RECEIVER)) == "stale_case"


def test_unknown_names_are_refused() -> None:
    service, _, case_id = started()
    assert error_code(lambda: service.answer("stranger", case_id, "ответ здесь")) == "not_found"
    assert error_code(lambda: service.phone("stranger")) == "not_found"
    assert error_code(lambda: service.start_scene("nothing")) == "not_found"
    assert error_code(lambda: service.case_file("BS-0000-0000")) == "not_found"


# -- matcher problems --------------------------------------------------------


@pytest.mark.parametrize("error", [MatcherError("no_matcher"), RuntimeError("boom")])
def test_no_matcher_answer_goes_to_a_person(error: Exception) -> None:
    service, _, case_id = started(matcher=StubMatcher(error))
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    service.answer("sender", case_id, BROTHER_SENDER)
    file = service.case_file(case_id)
    assert file["state"] == "with_specialist"
    assert file["reasons"] == ["matcher_unavailable"]


def test_a_comparison_that_never_ends_goes_to_a_person() -> None:
    class Lost:
        def submit(self, work: object) -> None:
            return None

    service, clock = make_service(executor=Lost())
    service.start_scene("brother")
    case_id = active_id(service)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    service.answer("sender", case_id, BROTHER_SENDER)
    assert service.case_file(case_id)["state"] == "comparing"
    clock.advance(seconds=61)
    assert service.case_file(case_id)["state"] == "with_specialist"


def test_a_late_comparison_does_not_touch_a_reset_case() -> None:
    from bothsides.cases.service import ThreadExecutor

    matcher = BlockingMatcher(gemini_result(0.95))
    service, _ = make_service(matcher, executor=ThreadExecutor())
    service.start_scene("brother")
    case_id = active_id(service)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    service.answer("sender", case_id, BROTHER_SENDER)
    assert matcher.started.wait(timeout=5)
    service.start_scene("brother")
    matcher.release.set()
    import time

    time.sleep(0.05)
    assert service.phone("receiver")["status"] == "question"


# -- deadlines ----------------------------------------------------------------


@pytest.mark.parametrize("who", ["receiver", "sender"])
def test_no_answer_before_the_deadline_goes_to_a_person(who: str) -> None:
    service, clock, case_id = started()
    if who == "sender":
        service.answer("receiver", case_id, BROTHER_RECEIVER)
    clock.advance(hours=23, minutes=59)
    assert service.phone(who)["status"] == "question"
    clock.advance(minutes=2)
    assert service.phone(who)["status"] == "with_specialist"
    assert service.case_file(case_id)["reasons"] == ["no_answer"]
    assert error_code(lambda: service.answer(who, case_id, BROTHER_RECEIVER)) == "wrong_step"


def test_open_case_is_marked_overdue_after_five_working_days() -> None:
    service, clock, case_id = held_case()
    assert service.case_file(case_id)["deadline_at"].startswith("2026-12-03T18:00")
    assert service.case_file(case_id)["overdue"] is False
    clock.advance(days=7, hours=5)
    assert service.case_file(case_id)["overdue"] is False
    clock.advance(hours=2)
    file = service.case_file(case_id)
    assert file["overdue"] is True
    assert file["state"] == "held"  # a deadline never ends a hold by itself


def test_closed_case_is_never_overdue() -> None:
    service, clock = make_service()
    file = run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    clock.advance(days=60)
    assert service.case_file(file["id"])["overdue"] is False


# -- denial -------------------------------------------------------------------


def test_one_tap_is_not_a_denial() -> None:
    service, clock, case_id = started("stranger")
    view = service.tap_deny(case_id)
    assert view["status"] == "question"
    assert 0 < view["deny_armed_seconds"] <= 4
    clock.advance(seconds=4.1)
    assert service.phone("receiver")["deny_armed_seconds"] == 0


@pytest.mark.parametrize(("gap", "denied"), [(0.2, True), (3.9, True), (4.0, True), (4.01, False), (30, False)])
def test_second_tap_must_come_within_four_seconds(gap: float, denied: bool) -> None:
    service, clock, case_id = started("stranger")
    service.tap_deny(case_id)
    clock.advance(seconds=gap)
    view = service.tap_deny(case_id)
    assert (view["status"] == "return_offer") is denied


def test_denial_offers_a_return_and_a_notice_with_the_case_number() -> None:
    service, clock, case_id = started("stranger")
    service.tap_deny(case_id)
    clock.advance(seconds=1)
    view = service.tap_deny(case_id)
    assert view["status"] == "return_offer"
    assert view["case_number"] == case_id
    assert service.phone("sender")["status"] == "question"
    assert service.case_file(case_id)["state"] == "with_specialist"
    assert service.case_file(case_id)["reasons"] == ["receiver_denied"]
    assert service.case_file(case_id)["denied"] is True


def test_accepting_the_offer_returns_the_money() -> None:
    service, clock, case_id = started("stranger")
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    clock.advance(seconds=3)
    assert service.accept_return(case_id)["status"] == "returned"
    assert service.phone("sender")["status"] == "returned"
    assert service.case_file(case_id)["state"] == "returned"


def test_return_needs_a_denial_first() -> None:
    service, _, case_id = started()
    assert error_code(lambda: service.accept_return(case_id)) == "wrong_step"


def test_denial_is_not_possible_after_an_answer() -> None:
    service, _, case_id = started()
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert error_code(lambda: service.tap_deny(case_id)) == "wrong_step"


def test_answer_is_not_possible_after_a_denial() -> None:
    service, _, case_id = started("stranger")
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    assert error_code(lambda: service.answer("receiver", case_id, "друг вернул долг")) == "wrong_step"
    service.answer("sender", case_id, "друг вернул долг")
    assert error_code(lambda: service.answer("sender", case_id, "друг вернул долг")) == "wrong_step"


def test_late_answer_with_a_coached_phrase_is_noted_for_the_specialist() -> None:
    service, _, case_id = started("stranger")
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    service.answer("sender", case_id, "мне сказали так сказать")
    file = service.case_file(case_id)
    assert file["reasons"] == ["receiver_denied", "coached_in_text"]
    assert file["state"] == "with_specialist"


@pytest.mark.parametrize(
    ("text", "reason"),
    [("я не знаю этого человека", "denial_in_text"), ("мне сказали так сказать", "coached_in_text"), ("бұл адамды танымаймын", "denial_in_text")],
)
@pytest.mark.parametrize("who", ["receiver", "sender"])
def test_typed_denial_goes_to_a_person_without_the_matcher(who: str, text: str, reason: str) -> None:
    matcher = StubMatcher(gemini_result(0.99))
    service, _, case_id = started(matcher=matcher)
    if who == "sender":
        service.answer("receiver", case_id, BROTHER_RECEIVER)
    service.answer(who, case_id, text)
    file = service.case_file(case_id)
    assert file["state"] == "with_specialist"
    assert file["reasons"] == [reason]
    assert file["denied"] is False
    assert matcher.calls == []


# -- holds and staff ----------------------------------------------------------


def test_clear_mismatch_by_the_language_model_is_held() -> None:
    service, _, case_id = held_case()
    file = service.case_file(case_id)
    assert file["reasons"][0] == "clear_mismatch"
    assert service.phone("receiver")["status"] == "held"
    assert service.phone("sender")["status"] == "held"


@pytest.mark.parametrize("side", ["receiver", "sender"])
def test_objection_is_recorded_once(side: str) -> None:
    service, clock, case_id = held_case()
    assert service.phone(side)["objection_sent"] is False
    assert service.object(side, case_id)["objection_sent"] is True
    clock.advance(minutes=1)
    service.object(side, case_id)
    file = service.case_file(case_id)
    assert [item["side"] for item in file["objections"]] == [side]
    assert file["state"] == "held"  # an objection never ends a hold by itself


def test_objection_needs_a_hold() -> None:
    service, _, case_id = started()
    assert error_code(lambda: service.object("sender", case_id)) == "wrong_step"


@pytest.mark.parametrize(("action", "state"), [("release", "credited"), ("return", "returned")])
def test_only_staff_ends_a_hold(action: str, state: str) -> None:
    service, clock, case_id = held_case()
    clock.advance(days=30)
    assert service.case_file(case_id)["state"] == "held"
    service.close_case(case_id, action)
    assert service.case_file(case_id)["state"] == state
    assert service.phone("receiver")["status"] == state
    assert service.case_file(case_id)["trail"][-1]["actor"] == "staff"


def test_staff_cannot_close_running_or_closed_cases() -> None:
    service, _, case_id = started()
    assert error_code(lambda: service.close_case(case_id, "release")) == "wrong_step"
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    assert error_code(lambda: service.close_case(case_id, "return")) == "wrong_step"
    service.answer("sender", case_id, BROTHER_SENDER)
    assert error_code(lambda: service.close_case(case_id, "return")) == "wrong_step"
    assert error_code(lambda: service.close_case(case_id, "delete")) == "not_found"


def test_trail_is_in_order_and_names_every_step() -> None:
    service, clock, case_id = started()
    clock.advance(seconds=5)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    clock.advance(seconds=5)
    service.answer("sender", case_id, BROTHER_SENDER)
    trail = service.case_file(case_id)["trail"]
    assert [entry["event"] for entry in trail] == [
        "transfer_stopped",
        "receiver_asked",
        "receiver_answered",
        "sender_asked",
        "sender_answered",
        "compared",
        "decided_release",
    ]
    times = [entry["at"] for entry in trail]
    assert times == sorted(times)


# -- repeated story -----------------------------------------------------------


def test_repeated_story_stops_a_release() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.97)))
    run_scene(service, "sister", BROTHER_RECEIVER, BROTHER_SENDER)
    run_scene(service, "stranger", BROTHER_RECEIVER, BROTHER_SENDER)
    file = run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    assert file["state"] == "with_specialist"
    assert file["reasons"] == ["repeated_story"]
    assert file["similar_receivers"] == 2


def test_running_the_same_scene_again_does_not_repeat_the_story() -> None:
    service, _ = make_service()
    for _ in range(3):
        assert run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)["state"] == "credited"


def test_reset_forgets_stories() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.97)))
    run_scene(service, "sister", BROTHER_RECEIVER, BROTHER_SENDER)
    run_scene(service, "stranger", BROTHER_RECEIVER, BROTHER_SENDER)
    service.reset()
    assert run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)["state"] == "credited"


def test_clock_in_tests_is_manual() -> None:
    assert ManualClock(START).now() == START
