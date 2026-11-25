"""Recognises common given names, so that they can be removed from an answer."""

from __future__ import annotations

from functools import lru_cache

from ..datafiles import load_json
from ..textnorm import fold_word
from .lexicon import names_a_relation

_VOWEL_ENDS = "аяьй"


def _fold(word: str) -> str:
    return fold_word(word.lower())


@lru_cache(maxsize=None)
def _name_forms() -> frozenset[str]:
    data = load_json("names")
    endings = tuple(_fold(ending) for ending in data["endings"])
    forms: set[str] = set()
    for name in (*data["kazakh"], *data["russian"], *data["english"]):
        folded = _fold(name)
        bases = {folded, folded[:-1]} if folded[-1] in _VOWEL_ENDS else {folded}
        forms |= {folded, *(base + ending for base in bases for ending in endings)}
    return frozenset(forms)


@lru_cache(maxsize=None)
def _surname_endings() -> tuple[str, ...]:
    return tuple(_fold(ending) for ending in load_json("names")["surname_endings"])


@lru_cache(maxsize=None)
def _not_names() -> frozenset[str]:
    return frozenset(load_json("names")["not_names"])


def is_relation_word(word: str) -> bool:
    """True for a relation, or another word as typed that only looks like a form of a name.

    "Қате" (by mistake) is not "Кате" (to Katya), so the typed letters count here.
    """
    return names_a_relation(_fold(word)) or word.lower() in _not_names()


def is_given_name(word: str) -> bool:
    """True for a listed given name in any common case form.

    "Жене" is a form of "Женя" and "to the wife": a relation is never taken for a name.
    """
    return _fold(word) in _name_forms() and not is_relation_word(word)


def is_name_part(word: str) -> bool:
    """True for an initial, a surname or a patronymic. Only means something next to a given name."""
    folded = _fold(word)
    return len(folded) <= 1 or (len(folded) >= 5 and folded.endswith(_surname_endings()))
