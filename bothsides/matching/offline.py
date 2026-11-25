"""Offline matcher: word features and a logistic function with fixed weights.

Known limit: it reads words, not sentences. The same listed reason on both
sides can pass even with a wrong relation or a common cover story. An answer
that denies something shares no reason and no relation here: the word list
cannot tell what is denied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from ..datafiles import load_json
from ..decision.content import informative_words
from ..textnorm import normalized
from .denials import has_negation
from .features import fuzzy_ratio, stem_overlap, trigram_cosine
from .lexicon import (
    Concepts,
    find_concepts,
    lists_too_many_reasons,
    relation_agreement,
    share_a_reason,
    weak_reasons,
)
from .types import MatchResult, MatchSource, Tri

_DENIED_NOTE = "Offline word list: an answer denies something; the list cannot tell what."


@lru_cache(maxsize=None)
def _weights() -> dict[str, float]:
    return load_json("matcher")["weights"]


@dataclass(frozen=True, slots=True)
class Features:
    """Everything the probability is made of. All values are 0 to 1."""

    stem_overlap: float
    trigram_cosine: float
    fuzzy_ratio: float
    shared_reason: float
    shared_half_only: float
    shared_half_extra: float
    reason_conflict: float
    relation_agrees: float
    relation_conflict: float


def _reason_conflict(receiver: Concepts, sender: Concepts) -> bool:
    own_receiver = receiver.reasons - weak_reasons()
    own_sender = sender.reasons - weak_reasons()
    return bool(own_receiver and own_sender and not own_receiver & own_sender)


def _is_denied(receiver_text: str, sender_text: str) -> bool:
    return has_negation(receiver_text) or has_negation(sender_text)


def _relation(receiver: Concepts, sender: Concepts, denied: bool) -> Tri:
    return Tri.UNKNOWN if denied else relation_agreement(receiver.relations, sender.relations)


def compute_features(receiver_text: str, sender_text: str) -> Features:
    """Compare the two answers word by word and concept by concept."""
    receiver, sender = find_concepts(receiver_text), find_concepts(sender_text)
    denied = _is_denied(receiver_text, sender_text)
    common = receiver.reasons & sender.reasons
    shared = share_a_reason(receiver_text, sender_text) and not denied
    full = shared and bool(common - weak_reasons())
    half_only = shared and not full
    agreement = _relation(receiver, sender, denied)
    left, right = normalized(receiver_text), normalized(sender_text)
    return Features(
        stem_overlap=stem_overlap(informative_words(receiver_text), informative_words(sender_text)),
        trigram_cosine=trigram_cosine(left, right),
        fuzzy_ratio=fuzzy_ratio(left, right),
        shared_reason=float(full),
        shared_half_only=float(half_only),
        shared_half_extra=float(full and bool(common & weak_reasons())),
        reason_conflict=float(_reason_conflict(receiver, sender)),
        relation_agrees=float(agreement is Tri.TRUE),
        relation_conflict=float(agreement is Tri.FALSE),
    )


def probability(features: Features) -> float:
    """Logistic function over the fixed weights."""
    weights = _weights()
    total = weights["bias"] + sum(weights[name] * getattr(features, name) for name in Features.__slots__)
    return 1.0 / (1.0 + math.exp(-total))


def _same_reason(receiver: Concepts, sender: Concepts, shared: bool) -> Tri:
    if shared:
        return Tri.TRUE
    if any(lists_too_many_reasons(side.reasons) for side in (receiver, sender)):
        return Tri.UNKNOWN
    # A weak reason (half of something, a purchase) does not say what for, so it contradicts nothing.
    return Tri.FALSE if _reason_conflict(receiver, sender) else Tri.UNKNOWN


def _note(receiver: Concepts, sender: Concepts, same_reason: Tri, same_relation: Tri) -> str:
    reason_text = {
        Tri.TRUE: "shared reason: " + ", ".join(sorted(receiver.reasons & sender.reasons)),
        Tri.FALSE: "different reasons",
        Tri.UNKNOWN: "no shared reason found",
    }[same_reason]
    relation_text = {
        Tri.TRUE: "relations agree",
        Tri.FALSE: "relations differ",
        Tri.UNKNOWN: "relation not named on both sides",
    }[same_relation]
    return f"Offline word list: {reason_text}; {relation_text}."


class OfflineMatcher:
    """Needs no network, no key and no packages."""

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        receiver, sender = find_concepts(receiver_text), find_concepts(sender_text)
        denied = _is_denied(receiver_text, sender_text)
        shared = share_a_reason(receiver_text, sender_text)
        same_reason = Tri.UNKNOWN if denied else _same_reason(receiver, sender, shared)
        same_relation = _relation(receiver, sender, denied)
        note = _DENIED_NOTE if denied else _note(receiver, sender, same_reason, same_relation)
        return MatchResult(
            probability=probability(compute_features(receiver_text, sender_text)),
            same_relation=same_relation,
            same_reason=same_reason,
            note=note,
            source=MatchSource.OFFLINE,
        )
