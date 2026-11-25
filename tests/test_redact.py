"""What is removed from an answer before it leaves the bank."""

from __future__ import annotations

import pytest

from bothsides.matching.redact import redact


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Айгуль, за аренду квартиры", "за аренду квартиры"),
        ("айгуль, за аренду квартиры", "за аренду квартиры"),
        ("Айгуль Серикова, за аренду", "за аренду"),
        ("Brother, half of the rent", "Brother, half of the rent"),
        ("Брат, за аренду", "Брат, за аренду"),
        ("Брату, моя половина аренды квартиры", "Брату, моя половина аренды квартиры"),
        ("Анам, оқуыма", "Анам, оқуыма"),
        ("Ағама, пәтер", "Ағама, пәтер"),
        ("Мой друг, вернул долг", "Мой друг, вернул долг"),
        ("За аренду, брат", "За аренду, брат"),
        ("Аренда, половина", "Аренда, половина"),
        ("Данияр, Айгуль, за обед", "Айгуль, за обед"),
    ],
)
def test_one_leading_name_goes_relations_stay(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("брату 90000 за аренду", "брату за аренду"),
        ("брату 90 000 тенге за аренду", "брату за аренду"),
        ("брату 90000тг за аренду", "брату за аренду"),
        ("брату 90к за аренду", "брату за аренду"),
        ("90 000 ₸ брату", "брату"),
        ("$100 to my brother", "to my brother"),
        ("100 USD to my brother", "to my brother"),
        ("сто тысяч тенге брату", "брату"),
        ("жүз мың теңге ағама", "ағама"),
        ("ninety thousand tenge to brother", "to brother"),
        ("брату ٩٠٠٠٠ за аренду", "брату за аренду"),
        ("брату ½ аренды", "брату аренды"),
        ("KZ12 3456 7890 брату", "брату"),
        ("карта 4400 4300 1111 2222 брату", "карта брату"),
        ("+7 701 123 45 67 брату", "брату"),
        ("mail a.b@example.com брату", "mail брату"),
        ("@nickname брату", "брату"),
        ("https://example.com/pay?x=1 брату", "брату"),
    ],
)
def test_amounts_accounts_and_contacts_go(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "90000", "90 000 ₸", "Данияр, 90000"])
def test_nothing_left(text: str) -> None:
    assert redact(text) == ""


def test_result_never_holds_a_digit() -> None:
    import unicodedata

    for text in ("a1b2c3", "аренда№5", "кв. 12, дом 7", "①②③ брату", "x² брату"):
        assert not any(unicodedata.category(ch) in {"Nd", "Nl", "No"} for ch in redact(text))


def test_ordinary_words_with_currency_letters_stay() -> None:
    assert redact("евродоставка для брата") == "евродоставка для брата"
    assert redact("тегеран поездка") == "тегеран поездка"
