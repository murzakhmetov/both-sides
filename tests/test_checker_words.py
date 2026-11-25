"""Found by an independent checker: wordings that slipped past the word lists. And honest
answers that must not suffer from the longer lists."""

from __future__ import annotations

import pytest

from bothsides.decision.content import has_content, informative_words
from bothsides.matching.denials import DenialKind, find_denial
from bothsides.matching.lexicon import word_concepts

from .helpers import active_id, make_service


def outcome(receiver: str, sender: str) -> str:
    service, _ = make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, receiver)
    if service.case_file(case_id)["state"] == "awaiting_sender":
        service.answer("sender", case_id, sender)
    return service.case_file(case_id)["state"]


DENIALS = [
    "никогда о нем не слышал, пришло за аренду квартиры",
    "первый раз о нём слышу",
    "впервые про неё слышу, за аренду",
    "мне не известен этот отправитель",
    "не имею понятия кто",
    "понятия не имеем, кто прислал",
    "не узнаю отправителя, за аренду квартиры",
    "не помню такого, пришло за аренду",
    "я с ним не общаюсь",
    "левый человек прислал за аренду",
    "случайный перевод, за аренду квартиры",
    "деньги пришли случайно",
    "деньги не мне",
    "танымаған адам пәтер ақысын жіберді",
    "таныған жоқпын",
    "ондай адамды көрген емеспін",
    "бөтен адам жіберді",
    "I cannot recognize this person, rent for the flat",
    "I can't recall who this is",
    "I haven't met this person",
    "no clue who sent it",
    "some random guy, rent",
    "first time I hear this name",
    "я его не помню",
    "ни знаю кто",
    "мне никто не должен был присылать",
    "кім жібергенін түсінбедім",
    "ондай туысым жоқ",
    "I have no relation to this person",
]
COACHED = [
    "должен сказать что брату за аренду квартиры",
    "мне велено говорить: брату за аренду",
    "мне подсказали: брату за аренду квартиры",
    "по инструкции пишу: брату за аренду",
    "меня научили: брату за аренду",
    "попросили указать брату за аренду",
    "айтқаным: ағама пәтер жалдау ақысы деп айт дейді",
    "солай деуді сұрады: ағама пәтер ақысы",
    "ағама пәтер ақысы деп айтуды тапсырды",
    "I was coached: rent for my brother",
    "I was advised to say rent for my brother",
    "as I was told, rent for my brother",
    "мне так объяснили: брату за аренду",
    "говорят пиши брату за аренду",
    "ағама пәтер ақысы де деп айтты",
    "following instructions: rent for my brother",
]


@pytest.mark.parametrize("text", DENIALS)
def test_denials_in_other_words(text: str) -> None:
    assert find_denial(text) is DenialKind.DENIAL
    assert outcome(text, "брату за аренду квартиры") == "with_specialist"


@pytest.mark.parametrize("text", COACHED)
def test_coached_answers_in_other_words(text: str) -> None:
    assert find_denial(text) is not None
    assert outcome("ағам пәтер жалдау ақысының жартысын жіберді", text) == "with_specialist"


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("друг занимался ремонтом дома", "другу вернул долг"),
        ("учитывая договор с братом прислал", "брату на учебу"),
        ("за пять футболок", "на футбол сыну"),
        ("после презентаций коллега", "коллеге подарок"),
        ("мама за десять столов", "маме на столовую"),
        ("школьный друг прислал", "школьному другу отправил"),
        ("аренда аренды", "аренду аренде"),
        ("аренда хахаха", "аренда хахаха"),
        ("аренда йцу", "аренда йцу"),
        ("брат скинул с телефона", "брату скинул с телефона"),
        ("ем у брата каждый день", "брату на лечение зубов"),
        ("операция с криптовалютой", "на операцию маме"),
        ("операционист помог брату", "брату на операцию"),
        ("аренда щас", "аренда щас"),
        ("друг доктор наук вернул", "другу на лечение"),
    ],
)
def test_look_alikes_and_fillers_release_nothing(receiver: str, sender: str) -> None:
    assert outcome(receiver, sender) == "with_specialist"


@pytest.mark.parametrize(
    ("word", "reason"),
    [("занимался", "debt"), ("учитывая", "tuition"), ("футболок", "sport"), ("презентаций", "gift"), ("столов", "food"), ("операционист", "treatment"), ("школьный", "tuition")],
)
def test_look_alikes_are_not_reasons(word: str, reason: str) -> None:
    assert reason not in word_concepts(word)


def test_two_forms_of_one_word_count_once() -> None:
    assert informative_words("аренда аренды") == ("аренда", "аренды")
    assert not has_content("аренда аренды")
    assert not has_content("брат брату братом")
    assert has_content("брат аренда")


@pytest.mark.parametrize(
    ("receiver", "sender"),
    [
        ("друг занимал, вернул долг", "другу вернул долг"),
        ("брат прислал на учебу", "брату на учебу"),
        ("папа за футбол", "сыну на футбол"),
        ("сестра прислала подарок", "сестре на подарок"),
        ("друг за обед в столовой", "другу за обед"),
        ("брат на новый телефон", "брату на телефон"),
        ("анам ем үшін жіберді", "дочери на лечение"),
        ("мама на операцию", "дочке на операцию"),
        ("брат прислал за школу дочки", "брату за школу"),
        ("сказал спасибо и вернул долг друг", "другу вернул долг"),
        ("ағаммен көптен көрген жоқпыз, пәтер ақысының жартысын жіберді", "брату за аренду квартиры, половина"),
        ("бөтен емес, туған ағам пәтер ақысын жіберді", "брату за аренду квартиры"),
        ("сестра на школьную форму", "сестре на школьную форму"),
        ("друг вернул долг, надо сказать не быстро", "другу вернул долг"),
        ("школьный друг вернул долг", "школьному другу вернул долг"),
    ],
)
def test_honest_answers_are_still_credited(receiver: str, sender: str) -> None:
    assert find_denial(receiver) is None and find_denial(sender) is None
    assert outcome(receiver, sender) == "credited"


def test_a_teacher_is_not_a_coach() -> None:
    assert find_denial("репетитору за уроки, он меня учил") is None
    assert find_denial("мен балаларды үйретіп жүрмін") is None
    assert find_denial("меня учили говорить так") is DenialKind.COACHED


@pytest.mark.parametrize(
    "answer",
    [
        "it is for personal needs, not related to work, from my wife for rent",
        "I do not remember the exact sum, mum sent it for utilities",
        "не помню точно сумму, за коммунальные услуги мама отправила",
        "не первый раз, мама каждый месяц на аренду",
        "балама сабақ үйретеді, қайтарған ақшасы",
        "my brother taught me to drive and paid for the license",
    ],
)
def test_an_honest_answer_is_not_a_denial(answer: str) -> None:
    assert find_denial(answer) is None


@pytest.mark.parametrize("answer", ["I do not remember who sent it", "can't recall this person", "I am not related to him at all"])
def test_not_remembering_a_person_is_a_denial(answer: str) -> None:
    assert find_denial(answer) is DenialKind.DENIAL
