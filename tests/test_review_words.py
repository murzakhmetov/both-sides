"""Word findings of the independent language review. Each test fails without its fix."""

from __future__ import annotations

import pytest

from bothsides.decision.content import has_content
from bothsides.decision.stories import is_similar_story
from bothsides.matching.denials import DenialKind, find_denial
from bothsides.matching.lexicon import find_concepts

from .helpers import make_service, run_scene


def state(receiver: str, sender: str) -> str:
    service, _ = make_service()
    return run_scene(service, "brother", receiver, sender)["state"]


@pytest.mark.parametrize(
    ("word", "concept"),
    [
        ("универсам", "tuition"),
        ("универсальный", "tuition"),
        ("должна", "debt"),
        ("ага", "brother"),
        ("ага", "aunt_uncle"),
        ("дарим", "treatment"),
        ("дарите", "treatment"),
        ("Дарина", "treatment"),
        ("Дарии", "treatment"),
        ("Женя", "spouse"),
        ("Женей", "spouse"),
        ("ул", "child"),
        ("доска", "friend"),
        ("маманға", "mother"),
        ("анада", "mother"),
        ("бата", "father"),
        ("тисе", "treatment"),
        ("колики", "car"),
        ("кузнецов", "relative"),
        ("кузнецова", "relative"),
        ("девушке", "grandparent"),
        ("система", "sister"),
        ("рождеством", "birthday"),
        ("починка", "funeral"),
        ("поминки", "repair"),
        ("учителю", "tuition"),
    ],
)
def test_word_is_not_this_concept(word: str, concept: str) -> None:
    found = find_concepts(word)
    assert concept not in found.relations | found.reasons


@pytest.mark.parametrize("text", ["ана жақта", "в другом городе", "по курсу доллара", "и др", "мне должна прийти"])
def test_phrase_without_a_relation_or_reason(text: str) -> None:
    found = find_concepts(text)
    assert found.relations == frozenset()
    assert found.reasons == frozenset()


@pytest.mark.parametrize(
    "text",
    ["ага, класс!", "я в курсе дела", "of course, thank you my dear", "подтверждаю операцию", "привет как дела чем занимаешься"],
)
def test_vague_sentence_on_both_phones(text: str) -> None:
    assert state(text, text) == "with_specialist"


@pytest.mark.parametrize(
    ("word", "concept"),
    [
        ("пәтерақысын", "rent"),
        ("патеракыга", "rent"),
        ("университетіме", "tuition"),
        ("курсқа", "tuition"),
        ("учусь", "tuition"),
        ("учится", "tuition"),
        ("дастарқанға", "food"),
        ("тамақтандық", "food"),
        ("обедали", "food"),
        ("ужинали", "food"),
        ("дәріханаға", "treatment"),
        ("лечат", "treatment"),
        ("лечусь", "treatment"),
        ("вылечить", "treatment"),
        ("зубного", "treatment"),
        ("взаймы", "debt"),
        ("задолжал", "debt"),
        ("задолженность", "debt"),
        ("қарыздарымды", "debt"),
        ("поровну", "half"),
        ("напополам", "half"),
        ("частями", "half"),
        ("друзьями", "friend"),
        ("анашым", "mother"),
        ("әкетай", "father"),
        ("экем", "father"),
        ("эпкеме", "sister"),
        ("інішегім", "brother"),
        ("зайыбыма", "spouse"),
    ],
)
def test_ordinary_forms_are_recognised(word: str, concept: str) -> None:
    found = find_concepts(word)
    assert concept in found.relations | found.reasons


@pytest.mark.parametrize("text", ["за мою еду", "на нашу еду", "купил еду", "был мне должен", "были должны друзья", "на д.р. подарок"])
def test_reasons_in_phrases(text: str) -> None:
    assert find_concepts(text).reasons


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("ағам пәтерақысын жіберді", "брату за аренду квартиры"),
        ("анам университетіме жіберді", "сыну на оплату университета"),
        ("әпкем курсқа жіберді", "сестре за курсы"),
        ("брат прислал на зубного", "брату на лечение зубов"),
        ("брат скинул за мою еду", "брату за еду"),
        ("Женя вернул за обед", "другу за обед"),
    ],
)
def test_honest_pairs_are_credited(receiver: str, sender: str) -> None:
    assert state(receiver, sender) == "credited"


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("Дарина скинула за такси", "сестре на лечение"),
        ("друг прислал на колледж", "сестре за колледж"),
        ("друг прислал на учебу", "дочке на учебу, она в другом городе"),
        ("телефон сатып алуға жіберді", "емге дәрі сатып алуға"),
        ("половина за кольцо", "половина за лечение"),
        ("друг половина за сауну", "другу половина за мебель"),
        ("досым соғымның жартысын жіберді", "другу половина аренды"),
    ],
)
def test_different_transfers_go_to_a_person(receiver: str, sender: str) -> None:
    assert state(receiver, sender) == "with_specialist"


@pytest.mark.parametrize(
    "text",
    [
        "танымаимын, маган ешким карыз емес",
        "таныс емеспін",
        "белгісіз адам",
        "кім бұл",
        "ошибся номером, аренду я не сдаю",
        "такого не знаю, квартиру никому не сдаю",
        "I don't know the sender",
        "sent by accident",
        "unknown",
    ],
)
def test_more_denials(text: str) -> None:
    assert find_denial(text) is DenialKind.DENIAL


@pytest.mark.parametrize(
    "text",
    [
        "мне сказали, чтобы я ответила сестре на лечение",
        "велели отвечать что сестре на лечение",
        "мне подсказывает мужчина по телефону, сестре на лечение",
        "сіңліме емге деп айт деп айтты",
        "сіңліме емге, солай айт дейді",
        "сіңліме емге, солай айтуға үйретті",
        "I was instructed to say it is for my sister",
        "следователь велел перевести",
    ],
)
def test_more_coached_answers(text: str) -> None:
    assert find_denial(text) is DenialKind.COACHED


@pytest.mark.parametrize(
    "text",
    [
        "я знаю кто это, мой брат за аренду",
        "не только знаю его, мы вместе живём, за аренду",
        "это не просто знакомый, это мой брат, за аренду",
        "это не по ошибке, брат прислал за аренду",
        "перевод не ошибочный, брат за аренду",
        "это не чужие деньги, брат вернул за аренду",
        "впервые вижу такую проверку, это брат за аренду",
        "қателеспесем, ағам пәтерге жіберді",
        "пәтер менікі емес, ағам екеуміз жалдаймыз",
        "таныс емес, туған ағам, пәтерге",
        "he is not a stranger, my brother",
        "следовательно, это за аренду брату",
        "друг подсказал врача, вернул за лечение",
    ],
)
def test_honest_answers_are_not_filed_as_denials(text: str) -> None:
    assert find_denial(text) is None


@pytest.mark.parametrize(
    "text",
    ["вернул должок", "қарыздарымды қайтарды", "қарызыңызды қайтардым", "ақшасына қайтарды", "аренда ага", "займ вернул"],
)
def test_other_forms_of_debt_and_money_carry_no_content(text: str) -> None:
    assert not has_content(text)


@pytest.mark.parametrize(
    ("first", "second", "similar"),
    [
        ("сестрёнке, посылаю на операцию", "сестре на лечение", True),
        ("әпкеме дәріханаға", "сестре на лечение", True),
        ("ағама пәтерақысына", "брату за аренду квартиры", True),
        ("брату моя половина", "ағама менің жартысы", True),
        ("сестре за аренду", "сестре на лечение", False),
        ("сестре на лечение зубов", "сестре на обучение зимой", False),
    ],
)
def test_similar_stories(first: str, second: str, similar: bool) -> None:
    assert is_similar_story(first, second) is similar
    assert is_similar_story(second, first) is similar
