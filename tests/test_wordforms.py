"""Two forms of one word count once, two words count twice."""

from __future__ import annotations

import pytest

from bothsides.decision.content import has_content, informative_words
from bothsides.decision.wordforms import distinct_words, same_word
from bothsides.textnorm import tokens

from .helpers import active_id, make_service

FORMS = [
    "аренда аренды аренде аренду арендой",
    "комната комнату комнатой",
    "билет билета билету билеты билетов билетами",
    "обед обеда обеды обедом",
    "еда еды еде еду едой",
    "чай чая чаю",
    "квартира квартиры квартиру квартирой",
    "лечение лечения лечению лечением",
    "операция операции операцию операцией",
    "подарок подарка подарку подарки подарков",
    "свадьба свадьбы свадьбу",
    "коммуналка коммуналки коммуналку",
    "лекарство лекарства лекарств лекарствам",
    "брат брата брату братом братья",
    "вернул вернула вернули",
    "пәтер пәтерге пәтерді пәтердің пәтерім пәтеріміз пәтеріне",
    "оқу оқуға оқуды оқуына",
    "көлік көлікке көлігім көліктің",
    "сыйлық сыйлығы сыйлыққа сыйлықтар",
    "мектеп мектебі мектепке",
    "аға ағам ағама ағамның",
    "rent rents rented renting",
    "ticket tickets",
]

DIFFERENT = [
    "квартирант квартиру",
    "арендатор аренду",
    "арендодателю аренду",
    "маникюрщице маникюр",
    "ремонтнику ремонт",
    "доставщику доставку",
    "пәтерші пәтерге",
    "таксисту такси",
    "квартплата квартиру",
    "учебник учебу",
    "школьник школу",
    "операция оператор",
    "продукты продавец",
    "телефон телевизор",
    "кредит кредитор",
    "оқу оқушы",
    "дәрі дәрігер",
    "ана анализ",
    "школа школьный",
    "renter rent",
]


def folded(text: str) -> tuple[str, ...]:
    return tokens(text)


@pytest.mark.parametrize("line", FORMS)
def test_forms_of_one_word(line: str) -> None:
    words = folded(line)
    apart = [(first, second) for first in words for second in words if not same_word(first, second)]
    assert apart == []
    assert len(distinct_words(words)) == 1


@pytest.mark.parametrize("line", DIFFERENT)
def test_two_words(line: str) -> None:
    first, second = folded(line)
    assert not same_word(first, second)
    assert has_content(line)


@pytest.mark.parametrize(
    "answer",
    [
        "аренда, за аренду",
        "аренду аренде",
        "обед, за обеды",
        "еда, за еду",
        "кредит, за кредиты",
        "аренда, моими деньгами",
        "аренда, своими деньгами",
        "за нашу аренду",
        "аренда okey",
        "аренда thx",
        "аренда хм",
        "аренда пж",
        "rent pls",
        "аренда йцуйцу",
        "rent asdasd",
        "йцуйцу фывфыв",
        "ляляля блабла",
        "аренда ляляля",
    ],
)
def test_one_word_and_fillers_go_to_a_person(answer: str) -> None:
    service, _ = make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, answer)
    service.answer("sender", case_id, answer)
    file = service.case_file(case_id)
    assert file["state"] == "with_specialist"
    assert "too_vague" in file["reasons"]


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("квартирант за квартиру", "хозяину за квартиру"),
        ("арендатор за аренду", "арендодателю за аренду"),
        ("клиентка за маникюр", "маникюрщице за маникюр"),
        ("клиент за доставку", "доставщику за доставку"),
        ("пәтерші пәтерге жіберді", "қожайынға пәтер үшін"),
    ],
)
def test_honest_pairs_with_related_words_are_credited(receiver: str, sender: str) -> None:
    service, _ = make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, receiver)
    service.answer("sender", case_id, sender)
    assert service.case_file(case_id)["state"] == "credited"


def test_a_word_is_kept_in_its_first_form() -> None:
    assert distinct_words(informative_words("брату за аренду, аренда для брата")) == ("брату", "аренду")
