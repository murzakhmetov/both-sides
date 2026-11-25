"""Gaps that an acceptance check against the brief confirmed, one test each."""

from __future__ import annotations

from pathlib import Path

import pytest

from bothsides.cases.transitions import apply_comparison, submit_receiver_answer, submit_sender_answer
from bothsides.matching.gemini import GeminiMatcher, parse_reply
from bothsides.matching.factory import MatcherStatus
from bothsides.matching.gemini_models import ModelState, choose_model
from bothsides.matching.lexicon import find_concepts
from bothsides.matching.names import is_given_name
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.redact import redact
from bothsides.matching.types import MatcherError, MatchResult, MatchSource, Tri
from evaluation import evaluate, live_check

from .fakes import FakeGeminiClient, StubMatcher, gemini_json, gemini_reply, gemini_result
from .helpers import SISTER_RECEIVER, SISTER_SENDER, active_id, make_service, run_scene

# -- the case file tells the truth on every way to a person ---------------------------------------


def service_with_two_similar_stories():
    service, clock = make_service()
    for scene in ("sister", "stranger"):
        run_scene(service, scene, SISTER_RECEIVER, SISTER_SENDER)
    service.start_scene("brother")
    return service, clock


def test_a_coached_sender_does_not_hide_the_repeated_story() -> None:
    service, _ = service_with_two_similar_stories()
    case_id = active_id(service)
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, "мне сказали так сказать: сестре на лечение")
    file = service.case_file(case_id)
    assert (file["state"], file["reasons"]) == ("with_specialist", ["coached_in_text"])
    assert file["similar_receivers"] == 2


@pytest.mark.parametrize("way", ["tap", "typed"])
def test_a_denial_does_not_hide_the_repeated_story(way: str) -> None:
    service, _ = service_with_two_similar_stories()
    case_id = active_id(service)
    if way == "tap":
        service.tap_deny(case_id)
        service.tap_deny(case_id)
    else:
        service.answer("receiver", case_id, "я не знаю этого человека")
    service.answer("sender", case_id, SISTER_SENDER)
    assert service.case_file(case_id)["similar_receivers"] == 2


def test_own_stories_of_the_receiver_are_not_counted() -> None:
    service, _ = make_service()
    for _ in range(3):
        file = run_scene(service, "sister", SISTER_RECEIVER, "мне сказали так сказать: сестре на лечение")
    assert file["similar_receivers"] == 0


def test_the_comparison_keeps_its_own_count() -> None:
    service, clock = make_service()
    service.start_scene("brother")
    board = service._board
    asked = submit_sender_answer(submit_receiver_answer(board.active, "брат за аренду", clock.now()), "брату за аренду", clock.now())
    compared = apply_comparison(asked, OfflineMatcher().compare("брат за аренду", "брату за аренду"), 4, clock.now())
    assert compared.similar_receivers == 4


def test_the_customer_never_sees_the_number_of_similar_stories() -> None:
    service, _ = service_with_two_similar_stories()
    case_id = active_id(service)
    service.answer("receiver", case_id, SISTER_RECEIVER)
    service.answer("sender", case_id, SISTER_SENDER)
    assert not any("similar" in key for side in ("receiver", "sender") for key in service.phone(side))


# -- seconds and thresholds on the screens ------------------------------------------------------------


def test_seconds_belong_to_the_decision_on_the_screen() -> None:
    service, clock = make_service()
    service.start_scene("sister")
    case_id = active_id(service)
    service.answer("receiver", case_id, SISTER_RECEIVER)
    clock.advance(seconds=3)
    service.answer("sender", case_id, SISTER_SENDER)
    assert service.stage()["seconds"] == 3.0
    clock.advance(seconds=12)
    service.close_case(case_id, "release")
    assert service.stage()["seconds"] == 15.0


@pytest.mark.parametrize(
    ("probability", "shown"),
    [(0.79995, 0.7999), (0.79999, 0.7999), (0.8, 0.8), (0.34996, 0.3499), (0.35, 0.35), (1.0, 1.0), (0.0, 0.0)],
)
def test_a_score_just_under_a_threshold_never_looks_like_it(probability: float, shown: float) -> None:
    result = MatchResult(probability, Tri.TRUE, Tri.TRUE, "", MatchSource.OFFLINE)
    assert result.shown_probability == shown
    service, _ = make_service(StubMatcher(gemini_result(probability)))
    file = run_scene(service, "brother", "брат за аренду", "брату за аренду")
    assert file["match"]["probability"] == shown
    compared = next(entry for entry in file["trail"] if entry["event"] == "compared")
    assert compared["details"][1] == f"{shown:.4f}"


# -- the staff note about half of something --------------------------------------------------------------


def test_half_of_the_same_unlisted_thing_is_open_not_different() -> None:
    result = OfflineMatcher().compare("брат прислал половину за диван", "брату половина за диван")
    assert result.same_reason is Tri.UNKNOWN
    assert "different reasons" not in result.note


def test_half_of_listed_different_things_is_different() -> None:
    assert OfflineMatcher().compare("половина аренды", "половина за лечение").same_reason is Tri.FALSE


# -- what the language model receives ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Жене, на продукты", "Жене, на продукты"),
        ("Жена, на продукты", "Жена, на продукты"),
        ("Моей жене, на продукты", "Моей жене, на продукты"),
        ("Жене Айгуль, на продукты", "Жене, на продукты"),
        ("Ана, оқуыма жіберді", "Ана, оқуыма жіберді"),
        ("Жеңге, тойға", "Жеңге, тойға"),
        ("Хозяину Серику, за аренду", "Хозяину, за аренду"),
        ("Кузина Айгуль, за билеты", "Кузина, за билеты"),
        ("Дәріге, анам жіберді", "Дәріге, анам жіберді"),
        ("Алматы, пәтер ақысы", "Алматы, пәтер ақысы"),
        ("Қате, бұл адамды танымаймын", "Қате, бұл адамды танымаймын"),
        ("Женя, за обед", "за обед"),
        ("Женей, за обед", "за обед"),
        ("Аня, за билеты", "за билеты"),
        ("Дария, оқуыма", "оқуыма"),
    ],
)
def test_relation_words_stay_and_names_go(text: str, expected: str) -> None:
    assert redact(text) == expected


def test_no_relation_or_reason_of_the_lexicon_is_taken_for_a_name() -> None:
    words = ["жена", "жене", "жену", "женой", "жены", "ана", "анам", "брат", "сестра", "дәріге", "хозяин", "бабушка", "әкем", "досым"]
    assert [word for word in words if is_given_name(word)] == []


@pytest.mark.parametrize(
    "text",
    [
        "брату 90000 tg за аренду",
        "брату 90000tg за аренду",
        "брату 90000 TNG за аренду",
        "брату полтысячи за аренду",
        "брату полторы тысячи за аренду",
        "брату сотню тысяч за аренду",
        "брату 500 дирхам за аренду",
        "брату 20 pounds за аренду",
        "брату копейки за аренду",
    ],
)
def test_more_amounts_and_currencies_go(text: str) -> None:
    assert redact(text) == "брату за аренду"


@pytest.mark.parametrize("word", ["бесжүз", "үшжүз", "тоғызжүз", "бесмың", "онмың", "екіжүзге"])
def test_kazakh_amounts_in_one_word_go(word: str) -> None:
    assert redact(f"ағама {word} пәтерге") == "ағама пәтерге"


@pytest.mark.parametrize("word", ["сумка", "лирика", "центр", "подсумок", "тигр"])
def test_ordinary_words_like_currencies_stay(word: str) -> None:
    assert word in redact(f"брату {word} за аренду")


def test_the_language_model_sees_the_wife() -> None:
    client = FakeGeminiClient(gemini_reply())
    GeminiMatcher(client, "gemini-fake").compare("муж прислал на продукты", "Жене, на продукты")
    assert "Жене, на продукты" in str(client.interactions.calls[0])


# -- the model list ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("listed", "model"),
    [
        (["gemini-flash-latest"], "gemini-flash-latest"),
        (["gemini-flash-latest", "gemini-1.5-flash-002"], "gemini-flash-latest"),
        (["gemini-3-flash-preview", "gemini-2.5-flash-preview-tts"], "gemini-3-flash-preview"),
        (["gemini-2.0-flash-001", "gemini-2.0-flash-live-001"], "gemini-2.0-flash-001"),
        (["gemini-flash-latest", "gemini-2.5-flash-lite"], "gemini-2.5-flash-lite"),
        (["gemini-2.5-flash-preview-09-2025", "gemini-flash-lite-latest"], "gemini-2.5-flash-preview-09-2025"),
    ],
)
def test_a_variant_is_taken_when_no_plain_flash_model_is_listed(listed: list[str], model: str) -> None:
    choice = choose_model(listed, "gemini-3.8-flash")
    assert (choice.model, choice.state) == (model, ModelState.REPLACED)


@pytest.mark.parametrize(
    "name",
    ["gemini-2.5-flash-image", "gemini-2.5-flash-preview-tts", "gemini-2.0-flash-live-001", "gemini-2.5-flash-native-audio-latest", "gemini-2.5-pro"],
)
def test_models_for_other_jobs_are_never_taken(name: str) -> None:
    assert choose_model([name], "gemini-3.8-flash").state is ModelState.UNCONFIRMED


def test_a_number_too_large_for_a_probability_is_invalid_json() -> None:
    with pytest.raises(MatcherError) as caught:
        parse_reply(gemini_json(probability=int("9" * 400)), "gemini-fake")
    assert caught.value.code == "invalid_json"


# -- words that look like a listed one ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "concept"),
    [
        ("отанда", "treatment"), ("отанға", "treatment"), ("отаннан", "treatment"), ("сыйластық", "gift"),
        ("подругому", "friend"), ("соседний", "neighbour"), ("шешеді", "mother"),
    ],
)
def test_more_lookalikes(word: str, concept: str) -> None:
    found = find_concepts(f"{word} болды")
    assert concept not in found.relations | found.reasons


def test_to_a_friend_is_a_friend_and_a_board_is_not() -> None:
    assert "friend" in find_concepts("досқа емге жібердім").relations
    assert "friend" not in find_concepts("доска для школы").relations


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [("отанда жүрмін, ағам жіберді", "брату на операцию"), ("ем обед с братом", "брату на лечение")],
)
def test_lookalikes_are_not_credited(receiver: str, sender: str) -> None:
    service, _ = make_service()
    assert run_scene(service, "brother", receiver, sender)["state"] == "with_specialist"


# -- the evaluation scripts -----------------------------------------------------------------------------------------


def test_a_sample_never_replaces_the_full_measurement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evaluate, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    assert evaluate.main(["--limit", "8"]) == 0
    assert [file.name for file in (tmp_path / "results").iterdir()] == ["offline-sample.json"]


def test_a_gemini_sample_never_replaces_the_full_measurement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Setup:
        language_model = StubMatcher(gemini_result(0.9))

        def confirm_model(self) -> None:
            """Nothing to ask."""

        def status(self) -> MatcherStatus:
            return MatcherStatus(active="gemini", reason="", model="gemini-fake")

    monkeypatch.setattr(evaluate, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(evaluate, "ROOT", tmp_path)
    monkeypatch.setattr(evaluate, "build_matcher", lambda offline, env: Setup())
    assert evaluate.main(["--gemini", "--limit", "8", "--pause", "0"]) == 0
    assert sorted(file.name for file in (tmp_path / "results").iterdir()) == ["gemini-sample.json", "offline-sample.json"]


@pytest.mark.parametrize("script", [evaluate, live_check], ids=["evaluate", "live_check"])
def test_the_scripts_explain_an_unreadable_env_file(
    script, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env").write_bytes("# ключ\n".encode("cp1251"))
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.main([]) == 2
    assert "Cannot start: " in capsys.readouterr().err
