"""Typed denials, coached phrases and negations. The word lists live in data/denials.json."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from ..datafiles import load_json
from ..textnorm import (
    Part,
    Phrase,
    clean,
    has_kazakh_letter,
    part_fits,
    phrase_at,
    read_phrase,
    tokens,
    typed_words,
)

#: In front of an exception they keep it from working: "не очень знаю кто это", "откуда я знаю кто это".
_BLOCKERS = frozenset(
    {"не", "ни", "нет", "откуда", "разве", "думаете", "думаешь", "not", "dont", "never", "никогда"}
)
_BLOCKER_REACH = 3

#: Right behind an exception they make it a question: "не ошибка ли это", "бейтаныс емес пе".
_QUESTION = frozenset({"ли", "па", "пе"})
_QUESTION_SIGNS = "?\u2753\u2754"


class DenialKind(str, Enum):
    """What kind of typed warning sign was found."""

    DENIAL = "denial"
    COACHED = "coached"


@dataclass(frozen=True, slots=True)
class _Group:
    phrases: tuple[Phrase, ...]
    max_gap: int


def _phrases(items: list[str]) -> tuple[Phrase, ...]:
    return tuple(read_phrase(item) for item in items)


def _parts(items: list[str]) -> Part:
    return tuple(item for phrase in _phrases(items) for part in phrase for item in part)


@lru_cache(maxsize=None)
def _group(kind: DenialKind) -> _Group:
    raw = load_json("denials")[kind.value]
    return _Group(_phrases([*raw["russian"], *raw["kazakh"], *raw["english"]]), raw["max_gap"])


@lru_cache(maxsize=None)
def _exceptions() -> tuple[Phrase, ...]:
    return _phrases(load_json("denials")["exceptions"])


@lru_cache(maxsize=None)
def _harmless_negations() -> tuple[Phrase, ...]:
    return _phrases(load_json("denials")["negation"]["exceptions"])


@lru_cache(maxsize=None)
def _negation_words() -> Part:
    raw = load_json("denials")["negation"]
    return _parts([*raw["russian"], *raw["kazakh"], *raw["english"]])


@lru_cache(maxsize=None)
def _kazakh_negative_verb() -> re.Pattern[str]:
    return re.compile(load_json("denials")["negation"]["kazakh_verb_pattern"])


@lru_cache(maxsize=None)
def _verb_lookalikes() -> Part:
    return _parts(load_json("denials")["negation"]["kazakh_verb_lookalikes"])


def _places(words: tuple[str, ...], phrases: tuple[Phrase, ...]) -> tuple[range, ...]:
    """Where the fixed phrases stand, questions left out."""
    return tuple(
        range(start, start + len(phrase))
        for phrase in phrases
        for start in range(len(words) - len(phrase) + 1)
        if phrase_at(words, start, phrase) and _QUESTION.isdisjoint(words[start + len(phrase) : start + len(phrase) + 1])
    )


def _is_blocked(words: tuple[str, ...], place: range, known: frozenset[int]) -> bool:
    """True for "не очень знаю кто это". A negation inside another fixed phrase does not count."""
    before = range(max(0, place.start - _BLOCKER_REACH), place.start)
    return any(words[index] in _BLOCKERS and index not in known for index in before)


def _covered(words: tuple[str, ...], phrases: tuple[Phrase, ...]) -> frozenset[int]:
    """Places of the fixed phrases that turn the meaning around ("не по ошибке")."""
    fixed = _places(words, (*_exceptions(), *_harmless_negations()))
    known = frozenset(index for place in fixed for index in place)
    places = _places(words, phrases)
    return frozenset(index for place in places if not _is_blocked(words, place, known) for index in place)


def _contains(words: tuple[str, ...], group: _Group) -> bool:
    return any(
        phrase_at(words, start, phrase, group.max_gap)
        for phrase in group.phrases
        for start in range(len(words))
    )


def _turned_around(text: str, words: tuple[str, ...]) -> frozenset[int]:
    """Places of the exceptions. "Это не ошибка? Пишут, за аренду" asks, so there are none."""
    asks = any(sign in clean(text) for sign in _QUESTION_SIGNS)
    return frozenset() if asks else _covered(words, _exceptions())


def find_denial(text: str) -> DenialKind | None:
    """Return the kind of denial typed in *text*, or None."""
    words = tokens(text)
    covered = _turned_around(text, words)
    kept = tuple(word for index, word in enumerate(words) if index not in covered)
    return next((kind for kind in DenialKind if _contains(kept, _group(kind))), None)


def _is_kazakh_or(typed: tuple[str, ...], index: int) -> bool:
    """True for the Kazakh "не" (or) between two Kazakh words. "не үшін" is on the list of exceptions."""
    if typed[index] != "не" or not 0 < index < len(typed) - 1:
        return False
    return has_kazakh_letter(typed[index - 1]) and has_kazakh_letter(typed[index + 1])


def _denies(typed: tuple[str, ...], words: tuple[str, ...], index: int) -> bool:
    word = words[index]
    if part_fits(word, _negation_words()):
        return not _is_kazakh_or(typed, index)
    return _kazakh_negative_verb().fullmatch(word) is not None and not part_fits(word, _verb_lookalikes())


@lru_cache(maxsize=1024)
def has_negation(text: str) -> bool:
    """True when an answer holds a negation, for example "не за аренду".

    Only the offline matcher asks: it reads words, not sentences, so it cannot tell
    which of them is denied.
    """
    typed, words = typed_words(text), tokens(text)
    covered = _turned_around(text, words) | _covered(words, _harmless_negations())
    return any(_denies(typed, words, index) for index in range(len(words)) if index not in covered)
