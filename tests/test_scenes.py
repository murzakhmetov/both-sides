"""The three demo scenes and the seeded background cases, with both matchers."""

from __future__ import annotations

import pytest

from bothsides.demo.scenes import SCENES
from bothsides.matching.types import Tri

from .fakes import StubMatcher, gemini_result
from .helpers import (
    BROTHER_RECEIVER,
    BROTHER_SENDER,
    SISTER_RECEIVER,
    SISTER_SENDER,
    active_id,
    make_service,
    run_scene,
)


def test_there_are_three_scenes_with_scripts() -> None:
    assert [scene.id for scene in SCENES] == ["brother", "sister", "stranger"]
    brother, sister, stranger = SCENES
    assert (brother.receiver_script, brother.sender_script) == (BROTHER_RECEIVER, BROTHER_SENDER)
    assert (sister.receiver_script, sister.sender_script) == (SISTER_RECEIVER, SISTER_SENDER)
    assert stranger.receiver_script == ""


def test_scene_one_brothers_rent_is_released_offline() -> None:
    service, _ = make_service()
    file = run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    assert file["state"] == "credited"
    assert file["reasons"] == []
    assert file["facts"]["risky"] == []


def test_scene_one_is_released_with_gemini() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.96)))
    assert run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)["state"] == "credited"


def test_scene_two_sister_story_goes_to_a_person_offline() -> None:
    service, _ = make_service()
    file = run_scene(service, "sister", SISTER_RECEIVER, SISTER_SENDER)
    assert file["state"] == "with_specialist"
    assert file["facts"]["account_age_days"] == 4
    assert file["facts"]["first_time_senders_today"] == 5
    assert len(file["facts"]["risky"]) >= 2
    assert "risky_facts" in file["reasons"]


def test_scene_two_sister_story_is_held_with_gemini() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.03, Tri.FALSE, Tri.FALSE)))
    assert run_scene(service, "sister", SISTER_RECEIVER, SISTER_SENDER)["state"] == "held"


def test_scene_two_is_not_released_even_when_the_model_is_fooled() -> None:
    service, _ = make_service(StubMatcher(gemini_result(1.0)))
    file = run_scene(service, "sister", SISTER_SENDER, SISTER_SENDER)
    assert file["state"] == "with_specialist"
    assert file["reasons"] == ["risky_facts"]


def test_scene_three_strangers_money() -> None:
    service, clock = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    clock.advance(seconds=2)
    view = service.tap_deny(case_id)
    assert view["status"] == "return_offer"
    assert view["case_number"].startswith("BS-2026-")


@pytest.mark.parametrize("text", ["asdf qwer", "спасибо большое", "бәрі жақсы рахмет"])
def test_same_nonsense_on_both_phones_offline(text: str) -> None:
    service, _ = make_service()
    assert run_scene(service, "brother", text, text)["state"] == "with_specialist"


@pytest.mark.parametrize("text", ["asdf qwer", "спасибо большое", "бәрі жақсы рахмет", "зелёный чайник поёт"])
@pytest.mark.parametrize("probability", [0.0, 0.2, 0.5, 0.99])
def test_same_nonsense_on_both_phones_with_gemini(text: str, probability: float) -> None:
    service, _ = make_service(StubMatcher(gemini_result(probability, Tri.UNKNOWN, Tri.UNKNOWN)))
    assert run_scene(service, "brother", text, text)["state"] == "with_specialist"


def test_choosing_a_scene_replaces_only_its_own_case() -> None:
    service, _ = make_service()
    run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    run_scene(service, "sister", SISTER_RECEIVER, SISTER_SENDER)
    service.start_scene("brother")
    by_scene = {item["scene"]: item["state"] for item in service.cases()["cases"] if item["scene"]}
    assert by_scene == {"brother": "awaiting_receiver", "sister": "with_specialist"}


def test_reset_gives_a_clean_board() -> None:
    service, _ = make_service()
    first = [item["state"] for item in service.cases()["cases"]]
    run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    run_scene(service, "sister", SISTER_RECEIVER, SISTER_SENDER)
    service.reset()
    assert [item["state"] for item in service.cases()["cases"]] == first
    assert service.stage()["scene"] == "brother"


def test_case_numbers_are_never_reused() -> None:
    service, _ = make_service()
    seen = {active_id(service)}
    for scene in ("brother", "brother", "sister", "stranger"):
        service.start_scene(scene)
        assert active_id(service) not in seen
        seen.add(active_id(service))
    service.reset()
    assert active_id(service) not in seen


def test_every_start_has_other_case_numbers() -> None:
    from bothsides.main import _first_number

    numbers = {_first_number() for _ in range(50)}
    assert len(numbers) > 20
    assert all(1_000 <= number < 9_000 for number in numbers)


def test_background_cases_show_every_console_state() -> None:
    service, _ = make_service()
    cases = [item for item in service.cases()["cases"] if item["scene"] is None]
    states = {item["state"] for item in cases}
    assert {"held", "with_specialist", "credited", "returned"} <= states
    assert any(item["overdue"] for item in cases)
    assert any(item["objections"] for item in cases)
    assert all(item["reasons"] for item in cases if item["state"] in {"held", "with_specialist"})


def test_background_cases_do_not_disturb_the_scenes() -> None:
    service, _ = make_service()
    file = run_scene(service, "brother", BROTHER_RECEIVER, BROTHER_SENDER)
    assert file["similar_receivers"] == 0
    file = run_scene(service, "sister", SISTER_RECEIVER, SISTER_SENDER)
    assert file["similar_receivers"] == 0
