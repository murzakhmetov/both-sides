"""Tells forms of one word from different words: "аренда" and "аренду", not "квартира" and "квартирант"."""

from __future__ import annotations

import re
from functools import lru_cache

from ..datafiles import load_json
from ..textnorm import fold_word, kazakh_suffix

#: A shared beginning must have so many letters. Two are enough when only a short ending
#: follows, verb endings need four ("стол" is not a form of "стоит").
_BASE_MIN_LENGTH = 3
_SHORT_BASE_LENGTH = 2
_VERB_BASE_MIN_LENGTH = 4

#: Letters that change before a Kazakh ending: мектеп - мектебі, сыйлық - сыйлығы (folded).
_SOFTENED = frozenset({("п", "б"), ("б", "п"), ("к", "г"), ("г", "к")})

#: "-қа" and "-та" follow voiceless letters only: "футболка" is not a form of "футбол" (футболға).
_HARD_SUFFIX = frozenset("кт")
_BEFORE_HARD_SUFFIX = frozenset("кпстфхцчшщбгд")

#: A vowel that other forms drop: подарок - подарка.
_FLEETING = re.compile(r"(?<=[бвгджзклмнпрстфхцчшщ])[ое]к$")


@lru_cache(maxsize=None)
def _endings(kind: str) -> frozenset[str]:
    return frozenset(fold_word(ending) for ending in load_json("wordforms")[kind])


def _shared_length(first: str, second: str) -> int:
    size = 0
    for left, right in zip(first, second):
        if left != right:
            break
        size += 1
    return size


def _are_kazakh_suffixes(base: str, *tails: str) -> bool:
    if base[-1:] not in _BEFORE_HARD_SUFFIX and any(tail[:1] in _HARD_SUFFIX for tail in tails if tail):
        return False
    return all(kazakh_suffix().fullmatch(tail) for tail in tails)


def _are_endings(base: str, first: str, second: str) -> bool:
    """True when both are endings of one language."""
    pair = {first, second}
    if pair <= _endings("russian") or pair <= _endings("english") or _are_kazakh_suffixes(base, first, second):
        return True
    softened = (first[:1], second[:1]) in _SOFTENED
    return softened and _are_kazakh_suffixes(base + "к", first[1:], second[1:])


def _same(first: str, second: str) -> bool:
    shared = _shared_length(first, second)
    tails = {first[shared:], second[shared:]}
    verb_sizes = range(shared, _VERB_BASE_MIN_LENGTH - 1, -1)
    for size in verb_sizes:
        tails_here = {first[size:], second[size:]}
        if tails_here <= _endings("verb") or tails_here <= _endings("kazakh_verb"):
            return True
    if shared == _SHORT_BASE_LENGTH and (tails <= _endings("short") or _are_kazakh_suffixes(first[:shared], *tails)):
        return True
    sizes = range(shared, _BASE_MIN_LENGTH - 1, -1)
    return any(_are_endings(first[:size], first[size:], second[size:]) for size in sizes)


@lru_cache(maxsize=4096)
def same_word(first: str, second: str) -> bool:
    """True for two forms of one folded word."""
    return _same(first, second) or _same(_FLEETING.sub("к", first), _FLEETING.sub("к", second))


def distinct_words(words: tuple[str, ...]) -> tuple[str, ...]:
    """Return the words, each word in one form only."""
    kept: tuple[str, ...] = ()
    for word in words:
        if not any(same_word(word, other) for other in kept):
            kept = (*kept, word)
    return kept
