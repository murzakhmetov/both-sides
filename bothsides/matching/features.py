"""Text features of the offline matcher. Plain arithmetic, easy to port."""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache

_STEM_ROUNDS = 3
_STEM_MIN = 3
_STEM_MAX = 5

_SUFFIXES = tuple(
    sorted(
        (
            # Russian endings
            "иями ями ами ого его ому ему ыми ими иях ях ах ией ей ой ий ый ая яя ое ее ые ие ую юю "
            "ом ем ам ям ов ев ия ью а я о е ы и у ю ь й "
            # Kazakh endings (folded)
            "нын нин дын дин тын тин нан нен дан ден тан тен мен бен пен га ге ка ке на не ды ди ты ти "
            "ны ни да де та те ым им ын ин сы си м н "
            # English endings
            "ing ed es s"
        ).split(),
        key=lambda suffix: (-len(suffix), suffix),
    )
)


def _strip_once(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _STEM_MIN:
            return word[: -len(suffix)]
    return word


@lru_cache(maxsize=4096)
def stem(word: str) -> str:
    """Cut endings and keep at most the first letters. Rough on purpose."""
    current = word
    for _ in range(_STEM_ROUNDS):
        shorter = _strip_once(current)
        if shorter == current:
            break
        current = shorter
    return current[:_STEM_MAX]


def stem_overlap(first: tuple[str, ...], second: tuple[str, ...]) -> float:
    """Dice overlap of the word stems, 0 to 1."""
    left = {stem(word) for word in first}
    right = {stem(word) for word in second}
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def _trigrams(text: str) -> Counter[str]:
    padded = f" {text} "
    return Counter(padded[i : i + 3] for i in range(len(padded) - 2))


def trigram_cosine(first: str, second: str) -> float:
    """Cosine of character-trigram counts, 0 to 1."""
    if not first or not second:
        return 0.0
    left, right = _trigrams(first), _trigrams(second)
    dot = sum(count * right[gram] for gram, count in left.items())
    norm = math.sqrt(sum(c * c for c in left.values()) * sum(c * c for c in right.values()))
    return min(1.0, dot / norm) if norm else 0.0


def _longest_common_subsequence(first: str, second: str) -> int:
    previous = [0] * (len(second) + 1)
    for char in first:
        current = [0]
        for index, other in enumerate(second):
            best = previous[index] + 1 if char == other else max(previous[index + 1], current[index])
            current.append(best)
        previous = current
    return previous[-1]


def fuzzy_ratio(first: str, second: str) -> float:
    """Similarity of the two texts with their words sorted, 0 to 1."""
    left = " ".join(sorted(first.split()))
    right = " ".join(sorted(second.split()))
    if not left or not right:
        return 0.0
    return 2 * _longest_common_subsequence(left, right) / (len(left) + len(right))
