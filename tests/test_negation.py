"""Denials that no list can spell out, and listed phrases that nothing may switch off."""

from __future__ import annotations

from itertools import product

import pytest

from bothsides.datafiles import load_json
from bothsides.matching.denials import DenialKind, find_denial, has_negation
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.types import Tri

from .fakes import StubMatcher, gemini_result
from .helpers import active_id, make_service

SENDER = "брату за аренду квартиры"
RECEIVER = "ағам пәтер жалдау ақысының жартысын жіберді"


def file_of(receiver: str, sender: str, matcher: object | None = None) -> dict[str, object]:
    service, _ = make_service(matcher=matcher) if matcher else make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, receiver)
    service.answer("sender", case_id, sender)
    return service.case_file(case_id)


# -- every listed phrase works inside a sentence ----------------------------------------------


def spellings(phrase: str) -> list[str]:
    """Every alternative of every place at least once; "*" alone stands for any word."""
    parts = [part.split("|") for part in phrase.split()]
    rounds = max(len(part) for part in parts)
    words = [[part[number % len(part)] for part in parts] for number in range(rounds)]
    return [" ".join(word.rstrip("*") or "вот" for word in row) for row in words]


@pytest.mark.parametrize("language", ["russian", "kazakh", "english"])
@pytest.mark.parametrize("kind", list(DenialKind))
def test_no_exception_switches_a_listed_phrase_off(kind: DenialKind, language: str) -> None:
    missed = [
        text
        for phrase in load_json("denials")[kind.value][language]
        for text in spellings(phrase)
        if find_denial(f"{text} человека, за аренду квартиры") is None
    ]
    assert missed == []


@pytest.mark.parametrize(
    "answer",
    [
        "первый раз вижу такого человека, за аренду квартиры",
        "впервые вижу такое имя, за аренду квартиры",
        "первый раз вижу такого человека, я квартиру не сдаю",
        "ни знаю кто это, прислал за квартиру",
        "не очень знаю кто это, прислал за аренду квартиры",
        "это не мне, я квартиру в аренду не сдаю",
        "не туда отправили, за аренду квартиры",
        "ни от кого денег не жду, за аренду квартиры",
        "хз кто перевел за аренду",
        "непонятно от кого пришло за аренду",
        "wrong number, rent for the flat",
        "who's this? rent for the flat",
        "I don‘t know him, rent for the flat",
        "I don´t know him, rent for the flat",
    ],
)
def test_common_denials_next_to_the_right_reason(answer: str) -> None:
    assert find_denial(answer) is DenialKind.DENIAL
    assert file_of(answer, SENDER)["reasons"] == ["denial_in_text"]


# -- a negation that no phrase covers -----------------------------------------------------------


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("это точно не за аренду квартиры", SENDER),
        ("я квартиру в аренду не сдаю, брат", SENDER),
        ("это не мой брат, за аренду квартиры", SENDER),
        ("у меня нет брата, и квартиру не снимаю", SENDER),
        ("не заню его, аренда квартиры", SENDER),
        ("ағам пәтер үшін жіберген жоқ", SENDER),
        ("бұл пәтер ақысы емес, ағам", SENDER),
        ("мен пәтер жалдамаймын, ағам жіберді", SENDER),
        ("i have no flat for rent", "rent for my brother"),
        ("this isnt rent, my brother", "rent for my brother"),
        (RECEIVER, "брату, но это не за квартиру"),
    ],
)
def test_the_word_list_never_credits_an_answer_that_denies_something(receiver: str, sender: str) -> None:
    file = file_of(receiver, sender)
    assert file["state"] == "with_specialist"
    assert "denial_in_text" in file["reasons"] or "no_shared_reason" in file["reasons"]


def test_what_the_word_list_says_about_a_negation() -> None:
    result = OfflineMatcher().compare("это не за аренду квартиры, брат", SENDER)
    assert (result.same_reason, result.same_relation) == (Tri.UNKNOWN, Tri.UNKNOWN)
    assert result.probability < 0.8
    assert "denies something" in result.note


def test_the_language_model_may_read_a_negation() -> None:
    file = file_of("не за еду, а за аренду, брат", SENDER, StubMatcher(gemini_result(0.96, Tri.TRUE)))
    assert file["state"] == "credited"


@pytest.mark.parametrize(
    "answer",
    [
        "не первый раз, брат за аренду квартиры",
        "бөтен емес, туған ағам пәтер ақысын жіберді",
        "я знаю кто это, мой брат, за аренду квартиры",
        "не только брат, вся семья платит за аренду квартиры",
        "my brother, not a stranger, rent for the flat",
    ],
)
def test_harmless_negations_are_still_credited(answer: str) -> None:
    assert find_denial(answer) is None and not has_negation(answer)
    assert file_of(answer, SENDER)["state"] == "credited"


@pytest.mark.parametrize(
    "answer",
    [
        "Жанбай ағам пәтерге жіберді",
        "Алмас ағам Алматыдан пәтерге",
        "апайдан кітапқа",
        "анама тамаққа жібердім",
        "әпкеммен бірге төледік",
        "памятник дедушке",
        "мамам помогает с учебой",
        "note for the teacher, November rent",
        "нотариусу за документы",
        "небольшой подарок племяннику",
    ],
)
def test_words_that_only_look_like_a_negation(answer: str) -> None:
    assert not has_negation(answer)


@pytest.mark.parametrize(
    "answer",
    ["алған жоқпын", "бермеді", "жалдамаймын", "көрмедім", "күтпедім", "сұрамаған", "танымаймыз", "ешкім емес", "dnt know", "ничего такого"],
)
def test_negations_are_found(answer: str) -> None:
    assert has_negation(answer)


# -- "they told me to say so" in any tense --------------------------------------------------------

RU_SPEAKERS = "сказал сказали говорит говорят велел велит просит просят попросили требует советуют научили".split()
RU_SAY = "скажи скажите пиши пишите напишите ответь отвечайте говори укажи назовите сказать писать ответить указать подтвердить".split()
EN_SPEAKERS = [
    "he told me to", "he tells me to", "he is telling me to", "they say to", "he asked me to", "he wants me to",
    "they made me", "I was told to", "I have to", "I must", "I should", "I am supposed to",
]
EN_SAY = "say write answer reply confirm".split()
KK_SAY = "айт айтыңыз айтшы айтыңызшы айтсын жаз жазыңыз деңіз жауап+бер жауап+беріңіз".split()
KK_SAID = ["деді", "дейді", "деп айтты", "деген", "десті"]


@pytest.mark.parametrize(
    ("first", "second", "tail"),
    [(RU_SPEAKERS, RU_SAY, "брату за аренду"), (EN_SPEAKERS, EN_SAY, "rent for my brother"), (KK_SAY, KK_SAID, "ағама пәтер ақысы")],
    ids=["russian", "english", "kazakh"],
)
def test_told_to_say_so_in_every_form(first: list[str], second: list[str], tail: str) -> None:
    texts = [f"{left} {right} {tail}".replace("+", " ") for left, right in product(first, second)]
    assert [text for text in texts if find_denial(text) is not DenialKind.COACHED] == []


@pytest.mark.parametrize(
    "answer",
    [
        "мама просила на лекарства, дорогие",
        "брат просил скинуть на бензин",
        "my daughter asked me to put money on her card for food",
        "my brother had to put down a deposit for the flat, rent",
        "капитан команды попросил на форму, за футбол",
        "клиентка за лечение, логопед учит сына говорить",
        "анам дәрігерге көрсет деді, емге жібердім",
        "құрбан айтқа деп анама жібердім",
        "непонятно почему остановили, брату за аренду квартиры",
    ],
)
def test_telling_about_somebody_is_not_coaching(answer: str) -> None:
    assert find_denial(answer) is None
