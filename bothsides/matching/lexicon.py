"""Finds relations and reasons in an answer with the shared word list.

Short stems match only with a listed ending, so "долго" is not "долг" and
"доставка" is not "дос". Look-alikes are excluded by name. The only typo that is
forgiven is two swapped letters: looser rules read "заплатил" as "зарплата".
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..datafiles import load_json
from ..decision.content import informative_words, is_stop_word
from ..textnorm import fold_word, kazakh_suffix, meaning_tokens
from .types import Tri

_TRANSPOSITION_MIN_LENGTH = 5


@dataclass(frozen=True, slots=True)
class Concept:
    """One relation or reason with everything needed to recognise it."""

    name: str
    group: str  # "relation" or "reason"
    words: frozenset[str]
    stems: tuple[tuple[str, str], ...]
    phrases: tuple[tuple[str, ...], ...]
    lookalikes: frozenset[str]
    lookalike_beginnings: tuple[str, ...]
    matches: frozenset[str]


@dataclass(frozen=True, slots=True)
class Concepts:
    """What was found in one answer."""

    relations: frozenset[str]
    reasons: frozenset[str]


def _fold(word: str) -> str:
    return fold_word(word.lower())


def _read_concept(name: str, group: str, raw: dict[str, Any], lookalikes: dict[str, Any]) -> Concept:
    words: list[str] = []
    stems: list[tuple[str, str]] = []
    phrases: list[tuple[str, ...]] = []
    for entry in raw["entries"]:
        if isinstance(entry, str):
            words.append(_fold(entry))
        elif isinstance(entry, dict):
            phrases.append(tuple(_fold(part) for part in entry["phrase"]))
        else:
            stems.append((_fold(entry[0]), entry[1]))
    return Concept(
        name=name,
        group=group,
        words=frozenset(words),
        stems=tuple(stems),
        phrases=tuple(phrases),
        lookalikes=frozenset(_fold(word) for word in lookalikes.get(name, ()) if not word.endswith("*")),
        lookalike_beginnings=tuple(_fold(word[:-1]) for word in lookalikes.get(name, ()) if word.endswith("*")),
        matches=frozenset(raw.get("matches", ())),
    )


@lru_cache(maxsize=None)
def lexicon_concepts() -> tuple[Concept, ...]:
    """All relations and reasons of the shared word list."""
    data = load_json("lexicon")
    lookalikes = load_json("lookalikes")
    relations = tuple(_read_concept(k, "relation", v, lookalikes) for k, v in data["relations"].items())
    reasons = tuple(_read_concept(k, "reason", v, lookalikes) for k, v in data["reasons"].items())
    return relations + reasons


@lru_cache(maxsize=None)
def _endings(kind: str) -> frozenset[str]:
    return frozenset(load_json("lexicon")["endings"][kind])


def _ending_fits(tail: str, kind: str) -> bool:
    if kind == "any":
        return len(tail) <= load_json("lexicon")["any_max_tail"]
    if kind == "kk":
        return kazakh_suffix().fullmatch(tail) is not None
    return tail in _endings(kind)


def _is_transposition(first: str, second: str) -> bool:
    if len(first) != len(second) or first == second:
        return False
    diff = [i for i, (a, b) in enumerate(zip(first, second)) if a != b]
    return (
        len(diff) == 2
        and diff[1] == diff[0] + 1
        and first[diff[0]] == second[diff[1]]
        and first[diff[1]] == second[diff[0]]
    )


def _has_swapped_letters(word: str, stem: str) -> bool:
    """True when *word* starts with *stem* and two neighbouring letters are swapped."""
    size = len(stem)
    return (
        size >= _TRANSPOSITION_MIN_LENGTH
        and 0 <= len(word) - size <= load_json("lexicon")["any_max_tail"]
        and word[0] == stem[0]
        and _is_transposition(word[:size], stem)
    )


def _is_lookalike(word: str, concept: Concept) -> bool:
    return word in concept.lookalikes or word.startswith(concept.lookalike_beginnings)


def _is_named_exactly(word: str, concept: Concept) -> bool:
    if _is_lookalike(word, concept):
        return False
    return word in concept.words or any(
        word.startswith(stem) and _ending_fits(word[len(stem) :], kind) for stem, kind in concept.stems
    )


def _is_named_with_typo(word: str, concept: Concept) -> bool:
    if _is_lookalike(word, concept):
        return False
    return any(kind == "any" and _has_swapped_letters(word, stem) for stem, kind in concept.stems)


@lru_cache(maxsize=4096)
def word_concepts(word: str) -> frozenset[str]:
    """Names of the concepts one folded word stands for."""
    exact = frozenset(c.name for c in lexicon_concepts() if _is_named_exactly(word, c))
    if exact or is_stop_word(word):
        return exact
    return frozenset(c.name for c in lexicon_concepts() if _is_named_with_typo(word, c))


@lru_cache(maxsize=None)
def _relation_names() -> frozenset[str]:
    return frozenset(concept.name for concept in lexicon_concepts() if concept.group == "relation")


def names_a_relation(word: str) -> bool:
    """True for a folded word like "брату" or "жене"."""
    return not _relation_names().isdisjoint(word_concepts(word))


def _part_fits(word: str, part: str) -> bool:
    return word.startswith(part[:-1]) if part.endswith("*") else word == part


def _has_phrase(words: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    last_start = len(words) - len(phrase)
    return any(
        all(_part_fits(words[start + i], part) for i, part in enumerate(phrase))
        for start in range(last_start + 1)
    )


@lru_cache(maxsize=1024)
def find_concepts(text: str) -> Concepts:
    """Return the relations and reasons named in *text*."""
    words = meaning_tokens(text)
    named = frozenset().union(*(word_concepts(word) for word in words))
    present = [
        concept
        for concept in lexicon_concepts()
        if concept.name in named or any(_has_phrase(words, phrase) for phrase in concept.phrases)
    ]
    return Concepts(
        relations=frozenset(c.name for c in present if c.group == "relation"),
        reasons=frozenset(c.name for c in present if c.group == "reason"),
    )


@lru_cache(maxsize=None)
def weak_reasons() -> frozenset[str]:
    """Half/share and the bare act of buying: they do not say what for."""
    return frozenset(load_json("matcher")["weak_reasons"])


def lists_too_many_reasons(reasons: frozenset[str]) -> bool:
    """True for an answer that names every possible reason to hit one of them."""
    return len(reasons - weak_reasons()) > load_json("matcher")["max_reasons"]


def shares_reason(first: frozenset[str], second: frozenset[str]) -> bool:
    """True when both answers name the same reason.

    "Half" alone counts only if not both sides name a different reason of
    their own: half of the rent is not half of a treatment.
    """
    if lists_too_many_reasons(first) or lists_too_many_reasons(second):
        return False
    common, weak = first & second, weak_reasons()
    if common - weak:
        return True
    if not common:
        return False
    return not (first - weak and second - weak)


def _own_words(text: str) -> tuple[str, ...]:
    """Informative words that are neither a relation nor a weak reason."""
    others = _relation_names() | weak_reasons()
    return tuple(word for word in informative_words(text) if not word_concepts(word) & others)


def share_a_reason(receiver_text: str, sender_text: str) -> bool:
    """The reason rule on two answers.

    "Half" alone does not count when both sides name something of their own,
    also when that something is not on the word list (half of a sofa).
    """
    first, second = find_concepts(receiver_text).reasons, find_concepts(sender_text).reasons
    if not shares_reason(first, second):
        return False
    if (first & second) - weak_reasons():
        return True
    return not (_own_words(receiver_text) and _own_words(sender_text))


def relation_agreement(receiver: frozenset[str], sender: frozenset[str]) -> Tri:
    """Compare relations seen from two sides (mother on one, son on the other)."""
    if not receiver or not sender:
        return Tri.UNKNOWN
    table = {concept.name: concept.matches for concept in lexicon_concepts() if concept.group == "relation"}
    return Tri.TRUE if any(table[name] & sender for name in receiver) else Tri.FALSE
