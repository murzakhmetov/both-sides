"""The content rule: each answer needs at least two informative words."""

from __future__ import annotations

import pytest

from bothsides.decision.content import has_content, informative_words


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "ok",
        "ок",
        "money",
        "деньги",
        "долг",
        "debt",
        "мой долг",
        "свой долг",
        "спасибо большое",
        "бәрі жақсы рахмет",
        "бари жаксы рахмет",
        "asdf qwer",
        "фыва йцук",
        "аааа оооо",
        "12345 90000",
        "for my money thanks",
        "брат брат",
        "перевод денег",
        "вернул долг",
        "қарызымды қайтарды ақша",
        "!!! ??? ...",
        "\U0001F600 \U0001F600",
        "фгкл вдрп",
    ],
)
def test_no_content(text: str) -> None:
    assert not has_content(text)


@pytest.mark.parametrize(
    "text",
    [
        "Брату, моя половина аренды квартиры",
        "ағам пәтер жалдау ақысының жартысын жіберді",
        "агам патер жалдау акысынын жартысын жиберди",
        "друг вернул долг",
        "сестре на лечение",
        "на день рождения",
        "my brother, rent",
        "анама дәрі",
    ],
)
def test_has_content(text: str) -> None:
    assert has_content(text)


def test_digits_are_not_words() -> None:
    assert informative_words("брату 90000 тенге 15") == ("брату",)


def test_repeated_words_count_once() -> None:
    assert informative_words("аренда аренда аренда") == ("аренда",)


def test_invisible_characters_do_not_make_words() -> None:
    assert not has_content("ok​ ​ok")
