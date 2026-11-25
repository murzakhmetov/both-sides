"""Small statistics for small sets. Standard library only."""

from __future__ import annotations

import math
import random
from typing import Sequence

_Z95 = 1.959964


def auc(positives: Sequence[float], negatives: Sequence[float]) -> float:
    """Chance that a random honest pair scores above a random other pair."""
    if not positives or not negatives:
        raise ValueError("both groups need at least one pair")
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def auc_interval(
    positives: Sequence[float], negatives: Sequence[float], rounds: int = 2000, seed: int = 7
) -> tuple[float, float]:
    """95% bootstrap interval of the AUC with a fixed seed."""
    source = random.Random(seed)
    samples = sorted(
        auc(source.choices(positives, k=len(positives)), source.choices(negatives, k=len(negatives)))
        for _ in range(rounds)
    )
    return samples[int(0.025 * rounds)], samples[int(0.975 * rounds) - 1]


def wilson(successes: int, total: int) -> tuple[float, float]:
    """95% interval of a rate, fair for small sets."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("need 0 <= successes <= total and total > 0")
    rate = successes / total
    factor = 1 + _Z95**2 / total
    center = (rate + _Z95**2 / (2 * total)) / factor
    half = _Z95 * math.sqrt(rate * (1 - rate) / total + _Z95**2 / (4 * total**2)) / factor
    return max(0.0, center - half), min(1.0, center + half)
