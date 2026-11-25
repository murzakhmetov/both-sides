"""Concepts found in Kazakh, Russian and English answers, and the look-alikes."""

from __future__ import annotations

import pytest

from bothsides.matching.lexicon import (
    find_concepts,
    lexicon_concepts,
    relation_agreement,
    shares_reason,
)
from bothsides.matching.types import Tri


@pytest.mark.parametrize(
    ("relation", "words"),
    [
        ("brother", "аға ағам ағама ағамнан агам брат брату братом братья братишке бауырым бауырыма іні ініме инисине brother bro"),
        ("sister", "әпке әпкем әпкеме апкеме сіңлі сіңліме синлиме сестра сестре сестрой сестренке қарындасым sister sis"),
        ("mother", "ана анам анама анамнан мама маме маму мамамнан мать матери мамочке шешем mother mom mum"),
        ("father", "әке әкем әкеме акемнен папа папе папы отец отцу бате father dad"),
        ("friend", "дос досым досыма досымнан друг другу другом друзьям подруга подруге құрбым friend buddy"),
        ("spouse", "муж мужу жена жене супруга күйеуім әйелім айелиме husband wife"),
        ("child", "сын сыну сыночку дочь дочери дочке ұлым ұлыма улымнан қызым қызыма кызыма son daughter"),
    ],
)
def test_relations(relation: str, words: str) -> None:
    for word in words.split():
        assert relation in find_concepts(word).relations, word


@pytest.mark.parametrize(
    ("reason", "texts"),
    [
        ("rent", ["пәтер", "пәтерге", "патер ушин", "аренда", "аренду", "квартира", "квартиры", "жалдау", "rent"]),
        ("half", ["жарты", "жартысын", "жартысы", "половина", "половину", "свою долю", "үлесім", "half", "share"]),
        ("debt", ["қарыз", "қарызымды", "карызын", "долг", "долга", "долгом", "debt"]),
        ("treatment", ["ем", "емге", "еміне", "емделуге", "лечение", "на лечение", "операция", "дәрі", "дәріге", "treatment"]),
        ("birthday", ["туған күн", "туған күніне", "туган кунине", "день рождения", "на др", "birthday"]),
        ("food", ["тамақ", "тамаққа", "продукты", "на еду", "за еду", "обед", "food", "groceries"]),
        ("tuition", ["оқу", "оқуға", "оқуына", "учеба", "за учебу", "обучение", "университет", "tuition"]),
        ("gift", ["сыйлық", "сыйлығы", "подарок", "подарки", "gift"]),
    ],
)
def test_reasons(reason: str, texts: list[str]) -> None:
    for text in texts:
        assert reason in find_concepts(text).reasons, text


@pytest.mark.parametrize(
    ("concept", "words"),
    [
        ("birthday", ["деньги", "денег", "день", "рождество"]),
        ("debt", ["долго", "долгий", "долгая", "занятие"]),
        ("friend", ["другой", "другому", "другие", "доставка", "доступ", "вдруг", "досье"]),
        ("brother", ["брать", "агент", "агентство"]),
        ("mother", ["анализ", "анализы", "материал", "математика", "ананас"]),
        ("father", ["папка", "папку", "батарея"]),
        ("child", ["улица", "улыбка", "қызыл", "баланс", "сынып"]),
        ("grandparent", ["атака", "апрель"]),
        ("treatment", ["ему", "емес", "емтихан", "Дарига"]),
        ("rent", ["рентген", "current", "parents"]),
        ("food", ["еду", "едем"]),
        ("wedding", ["той", "тойота"]),
        ("gift", ["презентация"]),
        ("sport", ["футболка"]),
        ("purchase", ["товарищу", "товарищ"]),
        ("car", ["резинка", "авторитет"]),
        ("tuition", ["окунь", "курсор"]),
        ("utilities", ["электричка"]),
    ],
)
def test_lookalikes(concept: str, words: list[str]) -> None:
    for word in words:
        found = find_concepts(word)
        assert concept not in found.relations | found.reasons, word


@pytest.mark.parametrize(
    ("text", "reason"),
    [("за квратиру", "rent"), ("за арнеду", "rent"), ("на лчеение", "treatment"), ("за продуткы", "food"), ("половниа", "half")],
)
def test_single_typos_in_long_words(text: str, reason: str) -> None:
    assert reason in find_concepts(text).reasons


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ({"rent"}, {"rent"}, True),
        ({"rent", "half"}, {"rent"}, True),
        ({"rent", "half"}, {"half"}, True),
        ({"half"}, {"half"}, True),
        ({"half", "rent"}, {"half", "treatment"}, False),
        ({"half", "rent", "food"}, {"half", "food"}, True),
        ({"debt"}, {"treatment"}, False),
        (set(), {"rent"}, False),
        (set(), set(), False),
    ],
)
def test_shared_reason_and_the_half_rule(first: set[str], second: set[str], expected: bool) -> None:
    assert shares_reason(frozenset(first), frozenset(second)) is expected
    assert shares_reason(frozenset(second), frozenset(first)) is expected


@pytest.mark.parametrize(
    ("receiver", "sender", "expected"),
    [
        ("ағам жіберді", "брату", Tri.TRUE),
        ("мама прислала", "сыну", Tri.TRUE),
        ("анам салды", "ұлыма", Tri.TRUE),
        ("сестра", "брату", Tri.TRUE),
        ("друг вернул", "сестре", Tri.FALSE),
        ("мама", "маме", Tri.FALSE),
        ("квартирант", "хозяину квартиры", Tri.TRUE),
        ("за аренду", "брату", Tri.UNKNOWN),
        ("", "", Tri.UNKNOWN),
    ],
)
def test_relations_are_seen_from_two_sides(receiver: str, sender: str, expected: Tri) -> None:
    agreement = relation_agreement(find_concepts(receiver).relations, find_concepts(sender).relations)
    assert agreement is expected


def test_relation_table_is_symmetric() -> None:
    concepts = {concept.name: concept for concept in lexicon_concepts() if concept.group == "relation"}
    for name, concept in concepts.items():
        for other in concept.matches:
            assert name in concepts[other].matches, (name, other)


def test_every_lookalike_group_names_a_real_concept() -> None:
    from bothsides.datafiles import load_json

    names = {concept.name for concept in lexicon_concepts()}
    assert {key for key in load_json("lookalikes") if key != "about"} <= names
