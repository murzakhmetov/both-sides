"""Typed denials and coached phrases in three languages."""

from __future__ import annotations

import pytest

from bothsides.matching.denials import DenialKind, find_denial


@pytest.mark.parametrize(
    "text",
    [
        "Я не знаю этого человека",
        "не знаю его вообще",
        "не знаю кто это и за что",
        "Незнакомый человек прислал",
        "я с ним не знаком",
        "впервые вижу это имя",
        "деньги пришли по ошибке",
        "ошибочный перевод",
        "Бұл адамды танымаймын",
        "бул адамды танымаймын",
        "кім екенін білмеймін",
        "бейтаныс адам",
        "қателесіп жіберген шығар",
        "I do not know this person",
        "I don't know him",
        "i dont know who sent it",
        "never met her",
        "some stranger sent it by mistake",
    ],
)
def test_denials(text: str) -> None:
    assert find_denial(text) is DenialKind.DENIAL


@pytest.mark.parametrize(
    "text",
    [
        "мне сказали так сказать",
        "они сказали сказать что сестре",
        "велели написать на лечение",
        "меня попросили сказать что брату",
        "под диктовку пишу",
        "следователь сказал перевести",
        "на безопасный счет",
        "солай айт деді",
        "осылай айтыңыз деді",
        "айтуымды сұрады",
        "жаз деді",
        "they told me to say so",
        "I was told to say it is for my sister",
        "he asked me to write this",
        "safe account",
    ],
)
def test_coached(text: str) -> None:
    assert find_denial(text) is DenialKind.COACHED


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Брату, моя половина аренды квартиры",
        "ағам пәтер жалдау ақысының жартысын жіберді",
        "друг вернул долг",
        "сестре на лечение",
        "хорошо знаю её, это моя сестра",
        "знакомая вернула за обед",
        "таныс қарызын қайтарды",
        "қарызымды қайтарамын деп айтты",
        "my brother sent his half of the rent",
        "мама сказала что скинет на учебу",
    ],
)
def test_ordinary_answers_are_not_denials(text: str) -> None:
    assert find_denial(text) is None


def test_denial_wins_over_coached() -> None:
    assert find_denial("не знаю этого человека, мне сказали так сказать") is DenialKind.DENIAL
