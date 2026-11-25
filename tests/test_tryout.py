"""The mini-demo of the landing page gives the verdict of the offline matcher and stores nothing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bothsides import config
from bothsides.cases.errors import ServiceError
from bothsides.cases.tryout import try_answers
from bothsides.decision.reasons import ReasonCode

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "shared" / "match_cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_same_verdict_as_the_shared_cases(case: dict[str, Any]) -> None:
    assert try_answers(case["receiver"], case["sender"]).view()["result"] == case["verdict"]


def test_the_mother_story_goes_to_a_specialist() -> None:
    result = try_answers("друг вернул долг", "сестре на лечение")
    assert not result.released
    assert ReasonCode.NO_SHARED_REASON in result.reasons


def test_half_of_different_things_goes_to_a_specialist() -> None:
    assert not try_answers("половина аренды", "половина за лечение").released


@pytest.mark.parametrize("text", ["asdf qwer", "спасибо большое", "бәрі жақсы рахмет"])
def test_the_same_nonsense_on_both_sides_is_never_a_match(text: str) -> None:
    assert not try_answers(text, text).released


@pytest.mark.parametrize(
    ("receiver", "sender", "reason"),
    [
        ("я не знаю этого человека", "брату на аренду квартиры", ReasonCode.DENIAL_IN_TEXT),
        ("брат прислал за аренду квартиры", "я не знаю этого человека", ReasonCode.DENIAL_IN_TEXT),
        ("мне велели сказать, что от сестры", "сестре на лечение", ReasonCode.COACHED_IN_TEXT),
        ("брат прислал за аренду квартиры", "мне позвонили из банка и велели так ответить", ReasonCode.COACHED_IN_TEXT),
    ],
)
def test_typed_denials_and_coached_phrases_count_on_both_sides(receiver: str, sender: str, reason: ReasonCode) -> None:
    result = try_answers(receiver, sender)
    assert not result.released
    assert result.reasons == (reason,)


def test_a_denial_and_a_coached_phrase_give_both_reasons() -> None:
    result = try_answers("я не знаю этого человека", "мне велели сказать, что сестре на лечение")
    assert not result.released
    assert set(result.reasons) == {ReasonCode.DENIAL_IN_TEXT, ReasonCode.COACHED_IN_TEXT}


def test_a_match_has_no_reasons() -> None:
    view = try_answers("ағам пәтер жалдау ақысының жартысын жіберді", "Брату, моя половина аренды квартиры").view()
    assert view == {"result": "match", "reasons": []}


@pytest.mark.parametrize(
    ("receiver", "sender", "code"),
    [
        ("", "брату на аренду", "empty_answer"),
        ("   ", "брату на аренду", "empty_answer"),
        ("брату на аренду", "а" * (config.MAX_ANSWER_LENGTH + 1), "too_long"),
    ],
)
def test_bad_answers_are_refused(receiver: str, sender: str, code: str) -> None:
    with pytest.raises(ServiceError) as error:
        try_answers(receiver, sender)
    assert (error.value.code, error.value.status) == (code, 400)
