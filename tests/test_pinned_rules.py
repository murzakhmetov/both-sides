"""Rules of the brief that a mutation review found unpinned. Each test kills its mutants."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta

import pytest

from bothsides import config
from bothsides.cases.errors import ServiceError
from bothsides.decision.content import has_content, informative_words
from bothsides.decision.gate import Outcome, decide
from bothsides.decision.stories import is_similar_story
from bothsides.demo.scenes import SCENES
from bothsides.matching.offline import Features, OfflineMatcher, probability
from bothsides.matching.types import MatchSource, Tri

from .fakes import StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER, active_id, make_service
from .test_gate import gate, match


def refused(call: object) -> str:
    with pytest.raises(ServiceError) as caught:
        call()  # type: ignore[operator]
    return caught.value.code


# -- decision rules ---------------------------------------------------------------------


def test_the_numbers_of_the_brief() -> None:
    assert config.RELEASE_PROBABILITY == 0.80
    assert config.HOLD_PROBABILITY == 0.35
    assert config.DENY_CONFIRM_WINDOW == timedelta(seconds=4)


@pytest.mark.parametrize("source", list(MatchSource))
@pytest.mark.parametrize("value", [0.36, 0.5, 0.65, 0.7, 0.79, 0.7999])
def test_below_the_threshold_a_person_decides_even_with_the_same_reason(source: MatchSource, value: float) -> None:
    assert decide(gate(match=match(value, source, Tri.TRUE))).outcome is Outcome.PERSON


def test_offline_needs_a_listed_reason_on_both_sides() -> None:
    result = OfflineMatcher().compare("брат прислал на адвоката", "брату на адвоката")
    assert result.probability >= config.RELEASE_PROBABILITY
    assert result.same_reason is not Tri.TRUE
    service, _ = make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, "брат прислал на адвоката")
    service.answer("sender", case_id, "брату на адвоката")
    file = service.case_file(case_id)
    assert (file["state"], file["reasons"]) == ("with_specialist", ["no_shared_reason"])


@pytest.mark.parametrize("word", ["ok", "money", "debt", "thanks", "for", "from", "мой", "свой", "деньги"])
def test_words_of_the_brief_carry_no_content(word: str) -> None:
    assert informative_words(word) == ()
    assert not has_content(f"{word} брату")


# -- offline features ----------------------------------------------------------------------

_LESS_LIKELY = {"reason_conflict", "relation_conflict"}


@pytest.mark.parametrize("name", [field.name for field in fields(Features)])
def test_every_feature_moves_the_probability(name: str) -> None:
    middle = Features(**{field.name: 0.5 for field in fields(Features)})
    low, high = replace(middle, **{name: 0.0}), replace(middle, **{name: 1.0})
    if name in _LESS_LIKELY:
        assert probability(high) < probability(low)
    else:
        assert probability(high) > probability(low)


# -- order and staff -----------------------------------------------------------------------


def test_an_early_sender_answer_changes_nothing() -> None:
    matcher = StubMatcher(gemini_result(0.97))
    service, _ = make_service(matcher)
    case_id = active_id(service)
    assert refused(lambda: service.answer("sender", case_id, BROTHER_SENDER)) == "wrong_step"
    file = service.case_file(case_id)
    assert (file["state"], file["sender_answer"]) == ("awaiting_receiver", None)
    assert service.phone("receiver")["status"] == "question"
    assert matcher.calls == []


def test_the_sender_gets_a_full_answer_window_too() -> None:
    service, clock = make_service()
    case_id = active_id(service)
    clock.advance(hours=20)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    answer_by = datetime.fromisoformat(service.phone("sender")["answer_by"])
    assert answer_by == clock.now() + config.ANSWER_WINDOW
    clock.advance(hours=23)
    assert service.phone("sender")["status"] == "question"


def with_result(probability_: float, reason: Tri) -> tuple[object, str]:
    service, _ = make_service(StubMatcher(gemini_result(probability_, reason, reason)))
    service.start_scene("sister")
    case_id = active_id(service)
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, SISTER_SENDER)
    return service, case_id


@pytest.mark.parametrize(
    ("value", "reason", "state"),
    [(0.5, Tri.FALSE, "with_specialist"), (0.02, Tri.FALSE, "held")],
)
def test_a_receiver_who_denied_nothing_cannot_return_the_money(value: float, reason: Tri, state: str) -> None:
    service, case_id = with_result(value, reason)
    assert service.case_file(case_id)["state"] == state  # type: ignore[attr-defined]
    assert refused(lambda: service.accept_return(case_id)) == "wrong_step"  # type: ignore[attr-defined]
    assert service.case_file(case_id)["state"] == state  # type: ignore[attr-defined]


def test_a_receiver_cannot_undo_what_a_specialist_decided() -> None:
    service, _ = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    service.close_case(case_id, "release")
    assert refused(lambda: service.accept_return(case_id)) == "wrong_step"
    assert service.case_file(case_id)["state"] == "credited"


@pytest.mark.parametrize(("action", "state", "event"), [("release", "credited", "staff_release"), ("return", "returned", "staff_return")])
def test_the_trail_names_the_staff_step_that_was_taken(action: str, state: str, event: str) -> None:
    service, case_id = with_result(0.5, Tri.FALSE)
    file = service.close_case(case_id, action)  # type: ignore[attr-defined]
    assert (file["state"], file["trail"][-1]["event"], file["trail"][-1]["actor"]) == (state, event, "staff")


@pytest.mark.parametrize(("value", "state"), [(0.5, "with_specialist"), (0.02, "held")])
def test_time_alone_never_ends_a_case_of_a_specialist(value: float, state: str) -> None:
    service, case_id = with_result(value, Tri.FALSE)
    clock = service._clock  # type: ignore[attr-defined]
    for days in (3, 7, 30, 365):
        clock.advance(days=days)
        assert service.case_file(case_id)["state"] == state  # type: ignore[attr-defined]
    assert service.case_file(case_id)["overdue"] is True  # type: ignore[attr-defined]


# -- repeated stories --------------------------------------------------------------------------


def test_stories_outside_the_word_list_are_similar_by_their_words() -> None:
    story = "вклад в новый проект Альфа"
    assert is_similar_story(story, "в новый проект Альфа, вклад")
    assert not is_similar_story(story, "ставка на матч в субботу")


def test_the_check_reads_the_story_of_the_sender() -> None:
    """Three receivers, three different answers, one story that the senders were told."""
    service, clock = make_service(StubMatcher(gemini_result(0.97)))
    receivers = {"brother": "подруга прислала за ужин", "stranger": "сын вернул за билеты", "sister": "коллега за подарок"}
    states = []
    for scene, answer in receivers.items():
        service.start_scene(scene)
        case_id = active_id(service)
        service.answer("receiver", case_id, answer)
        service.answer("sender", case_id, SISTER_SENDER)
        file = service.case_file(case_id)
        states.append((file["similar_receivers"], "repeated_story" in file["reasons"]))
        clock.advance(minutes=5)
    assert states == [(0, False), (1, False), (2, True)]


# -- what the screens show -----------------------------------------------------------------------


def test_each_phone_names_the_other_person_and_the_real_amount() -> None:
    service, _ = make_service()
    service.start_scene("brother")
    transfer = service.case_file(active_id(service))["transfer"]
    assert transfer["sender"] != transfer["receiver"]
    assert service.phone("receiver")["other_name"] == transfer["sender"]
    assert service.phone("sender")["other_name"] == transfer["receiver"]
    assert {service.phone(side)["amount"] for side in ("receiver", "sender")} == {transfer["amount"]}


@pytest.mark.parametrize(("value", "state"), [(0.5, "with_specialist"), (0.02, "held")])
def test_both_phones_show_the_deadline_of_the_decision(value: float, state: str) -> None:
    service, case_id = with_result(value, Tri.FALSE)
    deadline = service.case_file(case_id)["deadline_at"]  # type: ignore[attr-defined]
    for side in ("receiver", "sender"):
        view = service.phone(side)  # type: ignore[attr-defined]
        assert (view["status"], view["deadline_at"]) == (state, deadline)


def test_an_objection_belongs_to_one_phone() -> None:
    service, case_id = with_result(0.02, Tri.FALSE)
    service.object("receiver", case_id)  # type: ignore[attr-defined]
    sent = [service.phone(side)["objection_sent"] for side in ("receiver", "sender")]  # type: ignore[attr-defined]
    assert sent == [True, False]


def test_the_stage_shows_the_state_of_each_phone() -> None:
    service, _ = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    assert service.stage()["phones"] == {"receiver": "question", "sender": "waiting"}
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    assert service.stage()["phones"] == {"receiver": "return_offer", "sender": "question"}
    service.accept_return(case_id)
    assert service.stage()["phones"] == {"receiver": "returned", "sender": "returned"}


def test_the_screens_get_the_thresholds_of_the_config() -> None:
    service, _ = make_service()
    expected = {
        "release": config.RELEASE_PROBABILITY,
        "hold": config.HOLD_PROBABILITY,
        "repeated_story": config.REPEATED_STORY_RECEIVERS,
    }
    assert service.case_file(active_id(service))["thresholds"] == expected
    assert service.stage()["case"]["thresholds"] == expected


def test_names_come_in_the_language_of_the_key() -> None:
    service, _ = make_service()
    service.start_scene("brother")
    sender = next(scene for scene in SCENES if scene.id == "brother").transfer.sender
    expected = {"ru": sender.name_ru, "kk": sender.name_kk, "en": sender.name_en}
    assert len(set(expected.values())) > 1
    assert service.phone("receiver")["other_name"] == expected


def test_seconds_run_from_the_answer_of_the_receiver() -> None:
    service, clock = make_service()
    service.start_scene("brother")
    case_id = active_id(service)
    clock.advance(seconds=40)
    service.answer("receiver", case_id, BROTHER_RECEIVER)
    clock.advance(seconds=2)
    assert service.stage()["running_seconds"] == 2.0
    clock.advance(seconds=4)
    service.answer("sender", case_id, BROTHER_SENDER)
    assert service.stage()["seconds"] == 6.0
    assert service.case_file(case_id)["seconds"] == 6.0


def test_the_case_file_says_when_each_client_answered() -> None:
    service, clock = make_service()
    service.start_scene("brother")
    case_id = active_id(service)
    moments = []
    for side, text in (("receiver", BROTHER_RECEIVER), ("sender", BROTHER_SENDER)):
        clock.advance(seconds=30)
        service.answer(side, case_id, text)
        moments.append(clock.now())
    file = service.case_file(case_id)
    assert [datetime.fromisoformat(file[f"{side}_answer"]["at"]) for side in ("receiver", "sender")] == moments
