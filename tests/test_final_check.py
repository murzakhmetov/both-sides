"""Found by the last check: what a correction of the word lists broke, one test each."""

from __future__ import annotations

import pytest

from bothsides.decision.content import has_content
from bothsides.decision.wordforms import same_word
from bothsides.matching.denials import DenialKind, find_denial, has_negation
from bothsides.matching.lexicon import find_concepts
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.redact import redact
from bothsides.matching.types import MatchResult, MatchSource, Tri
from bothsides.textnorm import tokens, typed_words

from .helpers import make_service, run_scene

RU = "брату за аренду квартиры"
EN = "rent for my brother"


def state_of(receiver: str, sender: str) -> str:
    service, _ = make_service()
    return run_scene(service, "brother", receiver, sender)["state"]


# -- an exception covers its own words only --------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        ("I don't know exactly who this is, rent for the flat", DenialKind.DENIAL),
        ("I do not know exactly who sent it, rent for the flat", DenialKind.DENIAL),
        ("I don't know the exact person, rent for the flat", DenialKind.DENIAL),
        ("не знаю сколько и от кого, за аренду квартиры", DenialKind.DENIAL),
        ("не знаю сумму и отправителя, за аренду квартиры", DenialKind.DENIAL),
        ("не помню сколько и от кого, я его не помню, за аренду квартиры", DenialKind.DENIAL),
        ("откуда я знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("разве я знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("кім екенін білем бе, пәтер ақысы", DenialKind.DENIAL),
        ("сомасын білмеймін, адамын да, пәтер ақысы", DenialKind.DENIAL),
        ("не үшін келгенін түсінбей тұрмын, пәтер ақысы", DenialKind.DENIAL),
        ("мне велели сказать спасибо за аренду квартиры брату", DenialKind.COACHED),
        ("сказали: скажи спасибо, сестре на лечение", DenialKind.COACHED),
        ("брату за аренду квартиры, мне сказали так сказать. Спасибо", DenialKind.COACHED),
        ("rent for my brother, they told me to say. Thanks", DenialKind.COACHED),
        ("ағама пәтер ақысы, рахмет айт деді", DenialKind.COACHED),
        ("Не знаю. Сумма какая-то странная, пишут за аренду квартиры", DenialKind.DENIAL),
        ("бұл кісіні, соманы білмеймін, пәтер ақысы", DenialKind.DENIAL),
        ("не ошибка ли это, за аренду квартиры", DenialKind.DENIAL),
        ("не по ошибке ли прислали, за аренду квартиры", DenialKind.DENIAL),
        ("бейтаныс емес пе, пәтер ақысы", DenialKind.DENIAL),
        ("не думаю что знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("думаете я знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("думаешь я знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("нет уверенности что знаю кто это, за аренду квартиры", DenialKind.DENIAL),
        ("not sure it's not a mistake, rent for the flat", DenialKind.DENIAL),
        ("I don't think it's not a mistake, rent for the flat", DenialKind.DENIAL),
        ("көптен көрген жоқ па, пәтер ақысы", DenialKind.DENIAL),
        ("у нас развод на деньги, брат за аренду квартиры", DenialKind.DENIAL),
        ("маған солай айт, күнім деді, ағама пәтер жалдау ақысы", DenialKind.COACHED),
        ("ағама пәтер ақысы деп айт, күнім деді", DenialKind.COACHED),
        ("жіберуші таныс емес, туған күнге жіберіпті", DenialKind.DENIAL),
        ("Это не ошибка? Пишут, что за аренду квартиры", DenialKind.DENIAL),
        ("Это не ошибка\uff1f Пишут, что за аренду квартиры", DenialKind.DENIAL),
        ("is this not a mistake? rent for the flat", DenialKind.DENIAL),
        ("Это не ошибка\u2753 Пишут, что за аренду квартиры", DenialKind.DENIAL),
        ("ағама пәтер ақысы деп жаз, айыппұл болмасын деді", DenialKind.COACHED),
        ("ағама пәтер ақысы деп айт, мейрамға деді", DenialKind.COACHED),
        ("у нас развод судя по всему, за аренду квартиры", DenialKind.DENIAL),
        ("not just my money, rent for the flat", DenialKind.DENIAL),
        ("I never said not a stranger, rent for the flat", DenialKind.DENIAL),
        ("никогда не по ошибке такое, за аренду квартиры", DenialKind.DENIAL),
        ("бөтен адам емес деп айтады, пәтер ақысы", DenialKind.DENIAL),
        ("развод какой-то, за аренду квартиры", DenialKind.DENIAL),
    ],
)
def test_words_around_an_exception_still_count(answer: str, kind: DenialKind) -> None:
    assert find_denial(answer) is kind


@pytest.mark.parametrize(
    "answer",
    [
        "он мне не чужой, знаю кто это, брат за аренду квартиры",
        "если не ошибаюсь, знаю кто это, мой брат, за аренду квартиры",
        "не просто знаю кто это, это мой брат, за аренду квартиры",
        "not urgent, not a mistake, rent for my brother",
    ],
)
def test_a_negation_inside_another_fixed_phrase_blocks_nothing(answer: str) -> None:
    assert find_denial(answer) is None and not has_negation(answer)


def test_a_negation_far_away_blocks_nothing() -> None:
    assert find_denial("он не мог сам прийти вчера, знаю кто это, брат за аренду") is None


# -- "they told me to say so" in the future tense and without "to" ----------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "мне сказали, скажете что сестре на лечение",
        "сказали: если спросят, скажете сестре на лечение",
        "велели, если позвонят из банка, ответите сестре на лечение",
        "меня попросили, я сказал сестре на лечение",
        "просят, чтобы я ответила сестре на лечение",
        "he said tell the bank it is for my sister's treatment",
        "they asked me say it is for my sister, treatment",
        "they made me write treatment for my sister",
        "мне приказано: брату за аренду квартиры",
        "мне велено так, брату за аренду квартиры",
        "was told: rent for my brother",
        "I was advised: rent for my brother",
        "солай үйретті, ағама пәтер ақысы",
        "велели, вот и говорю: брату за аренду квартиры",
        "мне сказали, я и написала: брату за аренду квартиры",
        "he told me to put rent for my brother",
    ],
)
def test_coached_in_more_forms(answer: str) -> None:
    assert find_denial(answer) is DenialKind.COACHED


# -- words that deny nothing --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        # The Kazakh "не" is "what" or "or"; the bank's own question holds it.
        ("кім жіберді - ағам, не үшін - пәтер жалдауға", "Брату, моя половина аренды квартиры"),
        ("кім: ағам, не үшін: пәтерақы", RU),
        ("ким жиберди - агам, не ушин - патер", RU),
        ("ким? агам. не ушин? патер акысы", RU),
        ("тамаққа не киімге ағам жіберді", "інімнің тамағына"),
        # The number sign is not the English "no".
        ("брат за аренду квартиры №5", "брату за аренду"),
        ("мама прислала за садик №7", "дочери за садик №7"),
        ("my brother, rent for flat No 5", "rent of flat no. 5 for my brother"),
        # Ordinary words that end like a denying Kazakh verb.
        ("внук прислал подарок на День Победы", "дедушке подарок на День Победы"),
        ("сестра прислала на подарок, велосипеды детям", "сестре подарок детям, велосипеды"),
        ("ағам пәтер несиемді жабады", "ініме пәтер несиесіне"),
        ("ағам жанармайды төлеп берді", "брату за бензин"),
        ("Ол ағам. Ақша не үшін: пәтер ақысы", "брату за аренду квартиры"),
        ("брат за аренду квартиры на проспекте Победы", "брату за аренду квартиры"),
    ],
)
def test_answers_without_a_negation_are_credited(receiver: str, sender: str) -> None:
    assert not has_negation(receiver) and not has_negation(sender)
    assert state_of(receiver, sender) == "credited"


@pytest.mark.parametrize("word", ["велосипеды", "победы", "мопеды", "помады", "водопады", "логопеды", "тамады", "табады", "жабады", "көмеді"])
def test_words_that_end_like_a_denying_verb(word: str) -> None:
    assert not has_negation(f"{word} үшін")


@pytest.mark.parametrize(
    "answer",
    [
        "это не ағам прислал",
        "ағам не мой брат, пәтер ақысы",
        "брат ещё не берёт в аренду квартиру",
        "ағам пәтер не",
        "I have no 2 brothers, rent for the flat",
        "не әпкем, аренда",
        "я не за аренду",
        "айтпады",
        "жазбаған",
        "сатпаймын",
        "көнбеймін",
        "төлемедім",
        "жалдамай жүрмін",
        "жазбайды",
        "жазбайсың",
        "жазбапты",
        "сенбейді",
        "вряд ли за аренду",
        "мне не за что переводить",
        "no, it is for rent",
        "ағам емес",
    ],
)
def test_real_negations_are_still_found(answer: str) -> None:
    assert has_negation(answer)


def test_typed_words_and_tokens_stand_side_by_side() -> None:
    assert tokens("don′t") == tokens("don't")
    text = "Досқа №7, don´t, әпкем жіберді!"
    assert len(typed_words(text)) == len(tokens(text))
    assert typed_words(text) == ("досқа", "dont", "әпкем", "жіберді")


# -- names, as typed -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Кате, за билеты", "за билеты"),
        ("Моей сестре Кате, за билеты", "Моей сестре, за билеты"),
        ("Кате Ивановой, за билеты", "за билеты"),
        ("Дариге, за билеты", "за билеты"),
        ("Сергей Долгов, за билеты", "за билеты"),
        ("Андрей Зубов, за билеты", "за билеты"),
        ("Айгуль Школьникова, за билеты", "за билеты"),
        ("Сергей Внуков, за билеты", "за билеты"),
        ("Айгуль Кузина, за билеты", "за билеты"),
        ("Внуков Данияр, за билеты", "за билеты"),
        ("Қате, бұл адамды танымаймын", "Қате, бұл адамды танымаймын"),
        ("Дәріге, анам жіберді", "Дәріге, анам жіберді"),
        ("Хозяину Серику, за аренду", "Хозяину, за аренду"),
        ("Кузина Айгуль, за билеты", "Кузина, за билеты"),
    ],
)
def test_names_go_and_other_words_stay(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("сестра прислала за торт", "сестра прислала за торт"),
        ("Сестре на Торт", "Сестре на Торт"),
        ("брат прислал на СТО", "брат прислал на СТО"),
        ("брат прислал на сотку", "брат прислал на сотку"),
        ("ағама төрт мың пәтерге", "ағама пәтерге"),
        ("БРАТ ПРИСЛАЛ СТО ПЯТЬДЕСЯТ ТЫСЯЧ ЗА АРЕНДУ", "БРАТ ПРИСЛАЛ ЗА АРЕНДУ"),
        ("БРАТ ПРИСЛАЛ СТО ЗА АРЕНДУ", "БРАТ ПРИСЛАЛ ЗА АРЕНДУ"),
        ("агам торт жуз мын патерге жиберди", "агам патерге жиберди"),
        ("агама жуз торт тенге патерге", "агама патерге"),
        ("брату сто тысяч за аренду", "брату за аренду"),
        ("брату 500 som за аренду", "брату за аренду"),
        ("брату 500 еуро за аренду", "брату за аренду"),
        ("ағама 500 еуроға пәтер", "ағама пәтер"),
        ("брату 5 dirhams за аренду", "брату за аренду"),
    ],
)
def test_words_that_only_look_like_an_amount_stay(text: str, expected: str) -> None:
    assert redact(text) == expected


# -- small things ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("first", "second"), [("ем", "емге"), ("еми", "емге"), ("study", "studies"), ("подарил", "подарить"), ("свадьба", "свадьбой")])
def test_more_forms_of_one_word(first: str, second: str) -> None:
    assert same_word(first, second)


@pytest.mark.parametrize(("first", "second"), [("стол", "стоит"), ("банкет", "банки"), ("кабинет", "кабины"), ("газ", "газета"), ("флаг", "флакон"), ("қар", "карта")])
def test_short_beginnings_are_not_enough(first: str, second: str) -> None:
    assert not same_word(*tokens(f"{first} {second}"))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("поездку", "поезде"), ("плата", "платье"), ("платье", "платок"), ("воду", "водку"), ("плиту", "плитку"), ("пол", "полки"),
        ("маски", "масло"), ("мастер", "масло"), ("корм", "коров"), ("футболка", "футбол"), ("белое", "белье"), ("комната", "команда"),
        ("стену", "стенку"), ("кредит", "кредитку"), ("бананы", "баню"),
    ],
)
def test_different_words_with_a_shared_beginning(first: str, second: str) -> None:
    assert not same_word(first, second)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("сыйлады", "сыйлайды"), ("жалдады", "жалдайды"), ("емдейді", "емдеді"), ("salary", "salaries"), ("grocery", "groceries"), ("арендую", "арендовать"), ("обедал", "обедать"), ("одолжил", "одолжить"),
        ("подарит", "подарил"), ("починит", "починил"), ("орешек", "орешка"), ("платок", "платка"), ("мектеп", "мектебіне"),
    ],
)
def test_forms_of_verbs_and_plurals(first: str, second: str) -> None:
    assert same_word(*tokens(f"{first} {second}"))


@pytest.mark.parametrize("answer", ["за кускус и салат", "соус тартар", "couscous and salad", "bonbon cake", "хмель и солод"])
def test_real_words_with_repeated_letters_are_words(answer: str) -> None:
    assert has_content(answer)


def test_a_probability_a_hair_under_the_threshold() -> None:
    assert MatchResult(0.7999999999999, Tri.TRUE, Tri.TRUE, "", MatchSource.GEMINI).shown_probability == 0.7999


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [("половина за диван", "покупка дивана"), ("брат прислал мою половину", "брату за аренду квартиры")],
)
def test_a_weak_reason_contradicts_nothing(receiver: str, sender: str) -> None:
    result = OfflineMatcher().compare(receiver, sender)
    assert result.same_reason is Tri.UNKNOWN
    assert "different reasons" not in result.note


@pytest.mark.parametrize("word", ["Агата", "Агате", "Агату"])
def test_a_name_is_not_a_brother(word: str) -> None:
    assert find_concepts(f"{word} прислала").relations == frozenset()
