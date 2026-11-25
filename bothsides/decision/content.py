"""The content rule: an answer needs words that say something."""

from __future__ import annotations

import re
from functools import lru_cache

from .. import config
from ..datafiles import load_json
from ..textnorm import fold_word, meaning_tokens
from .wordforms import distinct_words

_VOWELS = frozenset("аеиоуыэюяaeiouy")
_NO_VOWEL_MIN_LENGTH = 4

#: "ляляля", "asdasd": letters typed again and again. "кускус" is food: two times is enough only for keyboard runs.
_REPEATED = re.compile(r"(.{2,4})\1{2,}")
_TWICE = re.compile(r"(.{3,4})\1")


@lru_cache(maxsize=None)
def _stop_words() -> tuple[frozenset[str], tuple[str, ...]]:
    """Folded stop words of all three languages: exact words and beginnings."""
    data = load_json("stopwords")
    words = [fold_word(word.lower()) for word in (*data["russian"], *data["kazakh"], *data["english"])]
    exact = frozenset(word for word in words if not word.endswith("*"))
    return exact, tuple(word[:-1] for word in words if word.endswith("*"))


@lru_cache(maxsize=4096)
def is_stop_word(word: str) -> bool:
    """True for a folded word that carries no content on its own."""
    exact, beginnings = _stop_words()
    return word in exact or word.startswith(beginnings)


@lru_cache(maxsize=None)
def _keyboard_rows() -> tuple[str, ...]:
    rows = tuple(load_json("stopwords")["keyboard_rows"])
    return rows + tuple(row[::-1] for row in rows)


def _is_keyboard_run(word: str) -> bool:
    if len(word) < load_json("stopwords")["keyboard_run_min_length"]:
        return False
    return any(word in row for row in _keyboard_rows())


def _is_noise(word: str) -> bool:
    if len(word) < 2 or len(set(word)) == 1:
        return True
    if len(word) >= _NO_VOWEL_MIN_LENGTH and not _VOWELS & set(word):
        return True
    if _REPEATED.fullmatch(word):
        return True
    twice = _TWICE.fullmatch(word)
    return _is_keyboard_run(word) or (twice is not None and any(twice.group(1) in row for row in _keyboard_rows()))


def informative_words(text: str) -> tuple[str, ...]:
    """Return the distinct folded words that carry content, in order."""
    kept = (word for word in meaning_tokens(text) if not is_stop_word(word) and not _is_noise(word))
    return tuple(dict.fromkeys(kept))


def has_content(text: str) -> bool:
    """True when the answer has enough informative words. Forms of one word count once."""
    return len(distinct_words(informative_words(text))) >= config.MIN_INFORMATIVE_WORDS
