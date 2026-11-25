"""The offline matcher: demo scenes, nonsense, half rule, features."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bothsides.config import RELEASE_PROBABILITY
from bothsides.decision.gate import GateInput, Outcome, decide
from bothsides.matching.features import fuzzy_ratio, stem, stem_overlap, trigram_cosine
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.types import MatchResult, MatchSource, Tri

CASES = json.loads((Path(__file__).parent / "shared" / "match_cases.json").read_text(encoding="utf-8"))["cases"]


def compare(receiver: str, sender: str) -> MatchResult:
    return OfflineMatcher().compare(receiver, sender)


def outcome(receiver: str, sender: str) -> Outcome:
    return decide(
        GateInput(
            match=compare(receiver, sender),
            receiver_text=receiver,
            sender_text=sender,
            risky_facts=0,
            similar_receivers=0,
        )
    ).outcome


def test_brother_rent_scene_matches_across_languages() -> None:
    result = compare("ағам пәтер жалдау ақысының жартысын жіберді", "Брату, моя половина аренды квартиры")
    assert result.source is MatchSource.OFFLINE
    assert result.probability >= RELEASE_PROBABILITY
    assert result.same_relation is Tri.TRUE
    assert result.same_reason is Tri.TRUE


def test_plain_letter_spelling_gives_the_same_verdict() -> None:
    with_letters = compare("ағам пәтер жалдау ақысының жартысын жіберді", "брату половина аренды")
    plain = compare("агам патер жалдау акысынын жартысын жиберди", "брату половина аренды")
    assert plain == with_letters


def test_sister_story_does_not_match() -> None:
    result = compare("друг вернул долг", "сестре на лечение")
    assert result.probability < 0.35
    assert result.same_relation is Tri.FALSE
    assert result.same_reason is Tri.FALSE


@pytest.mark.parametrize("text", ["asdf qwer", "спасибо большое", "бәрі жақсы рахмет", "привет как дела", "зелёный чайник поёт"])
def test_same_nonsense_on_both_phones_goes_to_a_person(text: str) -> None:
    assert outcome(text, text) is Outcome.PERSON


def test_half_of_different_things_goes_to_a_person() -> None:
    result = compare("половина аренды", "половина за лечение")
    assert result.same_reason is Tri.FALSE
    assert outcome("половина аренды", "половина за лечение") is Outcome.PERSON


def test_a_list_of_every_reason_is_not_an_answer() -> None:
    stuffed = "вернул долг за аренду лечение продукты подарок учебу"
    result = compare(stuffed, "сестре на лечение")
    assert result.same_reason is Tri.UNKNOWN
    assert outcome(stuffed, "сестре на лечение") is Outcome.PERSON
    assert outcome("сестре на лечение", stuffed) is Outcome.PERSON
    assert outcome(stuffed, stuffed) is Outcome.PERSON


def test_same_reason_with_conflicting_relation_goes_to_a_person() -> None:
    assert outcome("сестра вернула долг", "другу вернул долг") is Outcome.PERSON


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_shared_cases(case: dict[str, str]) -> None:
    expected = Outcome.RELEASE if case["verdict"] == "match" else Outcome.PERSON
    assert outcome(case["receiver"], case["sender"]) is expected


def test_probability_is_always_a_probability() -> None:
    texts = ["", "ok", "a" * 300, "аренда " * 40, "друг вернул долг", "😀", "половина"]
    for first in texts:
        for second in texts:
            assert 0.0 <= compare(first, second).probability <= 1.0


def test_matcher_note_holds_no_customer_text() -> None:
    assert "аренд" not in compare("брату аренда", "брат аренда").note.lower()


@pytest.mark.parametrize(
    ("first", "second"),
    [("аренда", "аренды"), ("квартира", "квартиру"), ("лечение", "лечения"), ("досым", "досыма"), ("қарызымды", "қарызын")],
)
def test_stems_meet(first: str, second: str) -> None:
    from bothsides.textnorm import fold_word

    assert stem(fold_word(first)) == stem(fold_word(second))


def test_features_at_the_edges() -> None:
    assert stem_overlap((), ()) == 0.0
    assert stem_overlap(("аренда",), ("аренды",)) == 1.0
    assert trigram_cosine("", "") == 0.0
    assert trigram_cosine("аренда", "аренда") == pytest.approx(1.0)
    assert fuzzy_ratio("", "") == 0.0
    assert fuzzy_ratio("абв", "абв") == 1.0
    assert fuzzy_ratio("абв", "где") == 0.0


def test_match_result_rejects_broken_probabilities() -> None:
    for bad in (float("nan"), float("inf"), -0.1, 1.1):
        with pytest.raises(ValueError):
            MatchResult(bad, Tri.TRUE, Tri.TRUE, "", MatchSource.OFFLINE)
