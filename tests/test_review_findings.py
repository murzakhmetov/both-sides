"""Defects found by independent reviewers. Each test fails without its fix."""

from __future__ import annotations

from datetime import date

import pytest

from bothsides.cases.deadlines import is_working_day
from bothsides.decision.content import has_content
from bothsides.decision.stories import is_similar_story
from bothsides.matching.chain import FallbackMatcher
from bothsides.matching.denials import DenialKind, find_denial
from bothsides.matching.gemini import GeminiMatcher
from bothsides.matching.lexicon import find_concepts
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.redact import redact
from bothsides.matching.types import MatcherError, Tri

from .fakes import FakeGeminiClient, StubMatcher, gemini_reply, gemini_result
from .helpers import BROTHER_RECEIVER, active_id, make_service, run_scene


def state(receiver: str, sender: str, scene: str = "brother") -> str:
    service, _ = make_service()
    return run_scene(service, scene, receiver, sender)["state"]


# -- words that looked like reasons -------------------------------------------------


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("заплатил за аренду квартиры", "заплатила за лечение зубов"),
        ("брат заплатил за ремонт", "заплатила сестре за лечение"),
        ("брат посылал деньги", "посылаю деньги брату"),
        ("друг за подработку", "другу на подарок"),
        ("мама прислала на колледж", "другу на колледж"),
        ("брат скидывал деньги", "брату скидывал деньги"),
        ("мама скидывает деньги", "скидываю сыну"),
    ],
)
def test_verbs_and_neighbours_are_not_reasons(receiver: str, sender: str) -> None:
    assert state(receiver, sender) == "with_specialist"


@pytest.mark.parametrize(
    ("word", "concept"),
    [
        ("заплатил", "salary"),
        ("посылал", "delivery"),
        ("подработку", "gift"),
        ("подработал", "gift"),
        ("колледж", "colleague"),
        ("скидывал", "half"),
        ("электронный", "utilities"),
        ("класс", "class_fund"),
    ],
)
def test_words_that_are_not_this_concept(word: str, concept: str) -> None:
    found = find_concepts(word)
    assert concept not in found.relations | found.reasons


@pytest.mark.parametrize(
    "text",
    [
        "я ем суп",
        "погода класс",
        "брат в курсе",
        "of course my friend",
        "обычная банковская операция",
        "перевод по номеру телефона",
        "через интернет банк",
        "электронный перевод на карту",
        "оплата кредитной картой",
    ],
)
def test_same_vague_sentence_on_both_phones_goes_to_a_person(text: str) -> None:
    assert state(text, text) == "with_specialist"


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("половина аренды", "половина за мебель"),
        ("брат половина за дрова", "брату половина аренды квартиры"),
        ("half of the sofa", "half of the insurance"),
        ("жартысы диванға", "жартысы пәтерге"),
    ],
)
def test_half_of_different_things_even_outside_the_word_list(receiver: str, sender: str) -> None:
    assert state(receiver, sender) == "with_specialist"


def test_half_on_one_side_still_counts() -> None:
    assert state("брат прислал половину за аренду", "брату моя половина") == "credited"


# -- typed denials ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "незнаю этого человека",
        "не знаю Ерлана",
        "Ерлана не знаю",
        "эту женщину не знаю",
        "не знаю, наверное за аренду",
        "I do not know the person",
        "Ерланды білмеймін",
        "бұл кісіні білмеймін",
        "неизвестный человек прислал",
        "чужой человек",
        "это ошибка",
        "who is this",
        "this is a mistake",
        "бұл кім",
        "мошенники какие-то",
        "танымайтын адам",
    ],
)
def test_everyday_denials(text: str) -> None:
    assert find_denial(text) is DenialKind.DENIAL


@pytest.mark.parametrize(
    "text",
    [
        "мне сказали, что надо так ответить: брату за аренду квартиры",
        "попросили говорить, что сестре на лечение",
        "мне так сказали: сестре на лечение",
        "I was asked to say it is half of the rent for my brother",
        "they said to say it is treatment for my sister",
        "маған солай айту керек деді, сіңліме емге",
        "велели в банке отвечать что брату",
    ],
)
def test_coached_phrases_with_words_in_between(text: str) -> None:
    assert find_denial(text) is DenialKind.COACHED


@pytest.mark.parametrize(
    "text",
    [
        "мама сказала что скинет на учебу",
        "друг обещал вернуть долг и вернул",
        "знаю его давно, брат",
        "таныс қарызын қайтарды",
        "қарызымды қайтарамын деп айтты",
        "my friend said thanks for dinner",
        "жена сказала оплатить садик",
        "брат попросил на ремонт",
        "other person, my brother",
    ],
)
def test_ordinary_answers_stay_ordinary(text: str) -> None:
    assert find_denial(text) is None


def test_named_denial_is_not_released() -> None:
    assert state("не знаю Ерлана, за аренду квартиры", "за аренду квартиры") == "with_specialist"


# -- what leaves the bank ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Неизвестный, за аренду квартиры",
        "Алименты, за ноябрь",
        "Страховка, за ноябрь",
        "Родители, за аренду",
        "Отчим, за аренду",
        "Жеңгем, пәтер ақысы",
        "Туысқаным, пәтер ақысы",
        "Mama, for rent",
        "Мебель, половина",
    ],
)
def test_only_names_are_removed(text: str) -> None:
    assert redact(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Айгуль С., за аренду", "за аренду"),
        ("Ахметова Айгуль Сериковна, за аренду", "за аренду"),
        ("айгуль серикова, за аренду", "за аренду"),
        ("Женя, за аренду", "за аренду"),
        ("Дарина, за аренду", "за аренду"),
        ("«Данияр», за аренду", "за аренду"),
        ("— Данияр, за аренду", "за аренду"),
        ("Ерлан ағам, пәтер ақысы", "ағам, пәтер ақысы"),
        ("Даниярға, пәтер ақысы", "пәтер ақысы"),
    ],
)
def test_names_in_other_shapes_are_removed(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("брату пятнадцать тысяч тенге за аренду", "брату за аренду"),
        ("около девяноста тысяч за аренду", "около за аренду"),
        ("двести-триста тысяч за аренду", "за аренду"),
        ("ағама он бес мың теңге", "ағама"),
        ("twenty-five thousand to my brother", "to my brother"),
        ("вернул долг 200 долларами", "вернул долг"),
        ("90 мың теңгені қайтардым", "қайтардым"),
        ("100 баксов брату", "брату"),
        ("200 USDT брату", "брату"),
        ("рублями брату", "брату"),
        ("t.me/arman_k брату", "брату"),
        ("instagram.com/arman.k брату", "брату"),
        ("kaspi.kz/pay/arman брату", "брату"),
        ("почта arman.k @ mail.ru брату", "почта брату"),
    ],
)
def test_amounts_in_words_and_links_go(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize("text", ["@аренда @квартиры", "www.аренда.квартиры", "t.me/аренда брат@mail.kz"])
def test_contacts_carry_no_content(text: str) -> None:
    assert not has_content(text)
    assert find_concepts(text).reasons == frozenset()


def test_an_answer_that_is_empty_after_cleaning_never_reaches_the_offline_matcher() -> None:
    client = FakeGeminiClient(gemini_reply())
    chain = FallbackMatcher(GeminiMatcher(client, "m"), StubMatcher(gemini_result(0.99)))
    with pytest.raises(MatcherError) as caught:
        chain.compare("@аренда @квартиры", "друг, за аренду квартиры")
    assert caught.value.code == "empty"
    assert client.interactions.calls == []


def test_contacts_instead_of_an_answer_go_to_a_person() -> None:
    client = FakeGeminiClient(gemini_reply(probability=0.99))
    service, _ = make_service(FallbackMatcher(GeminiMatcher(client, "m"), OfflineMatcher()))
    file = run_scene(service, "brother", "Друг, за аренду квартиры", "@аренда @квартиры")
    assert file["state"] == "with_specialist"
    assert file["reasons"] == ["too_vague"]


# -- workflow -----------------------------------------------------------------------------


@pytest.mark.parametrize("route", ["tap", "typed"])
def test_sender_cannot_tell_a_denial_from_a_mismatch(route: str) -> None:
    service, _ = make_service()
    service.start_scene("sister")
    case_id = active_id(service)
    statuses = [service.phone("sender")["status"]]
    if route == "tap":
        service.tap_deny(case_id)
        service.tap_deny(case_id)
    else:
        service.answer("receiver", case_id, "я не знаю этого человека")
    statuses.append(service.phone("sender")["status"])
    service.answer("sender", case_id, "сестре на лечение")
    statuses.append(service.phone("sender")["status"])
    assert statuses == ["waiting", "question", "with_specialist"]
    file = service.case_file(case_id)
    assert file["sender_answer"]["text"] == "сестре на лечение"
    assert file["match"] is None
    assert file["reasons"] == ["receiver_denied" if route == "tap" else "denial_in_text"]


def test_sender_is_not_asked_after_the_money_went_back() -> None:
    service, _ = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    assert service.phone("sender")["status"] == "question"
    service.accept_return(case_id)
    assert service.phone("sender")["status"] == "returned"


def test_sender_question_after_a_denial_ends_with_the_answer_window() -> None:
    service, clock = make_service()
    service.start_scene("stranger")
    case_id = active_id(service)
    service.tap_deny(case_id)
    service.tap_deny(case_id)
    clock.advance(hours=24, minutes=1)
    assert service.phone("sender")["status"] == "with_specialist"


def test_the_trail_never_rounds_a_score_to_a_threshold() -> None:
    service, _ = make_service(StubMatcher(gemini_result(0.7999)))
    file = run_scene(service, "brother", BROTHER_RECEIVER, "брату за аренду квартиры")
    compared = next(entry for entry in file["trail"] if entry["event"] == "compared")
    assert compared["details"] == ["gemini", "0.7999"]


def test_a_missed_answer_is_dated_at_its_deadline() -> None:
    service, clock = make_service()
    service.start_scene("brother")
    case_id = active_id(service)
    clock.advance(days=3)
    file = service.case_file(case_id)
    assert file["decided_at"] == file["answer_by"]


@pytest.mark.parametrize("day", [date(2027, 5, 3), date(2027, 5, 10)])
def test_moved_days_off_in_may(day: date) -> None:
    assert not is_working_day(day)


# -- repeated story ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("за аренду квартиры", "пәтер жалдау ақысы"),
        ("сестре на лечение", "сіңліме емге және азық-түлікке"),
        ("сестре на лечение", "сестре Айгуль на операцию, она лежит в больнице, и немного на продукты"),
    ],
)
def test_same_story_in_other_words_or_with_one_more_reason(first: str, second: str) -> None:
    assert is_similar_story(first, second)
    assert is_similar_story(second, first)


def test_other_person_or_other_reason_is_another_story() -> None:
    assert not is_similar_story("сестре на лечение", "брату за аренду")
    assert not is_similar_story("сестре на лечение", "сестре на учебу")


def test_offline_matcher_still_knows_single_swapped_letters() -> None:
    assert "rent" in find_concepts("за квратиру").reasons
    assert OfflineMatcher().compare("за квратиру брат", "брату квартира").same_reason is Tri.TRUE
