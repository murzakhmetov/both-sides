"""Repeated-story check: the same sender story for several receivers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .. import config
from ..matching.features import trigram_cosine
from ..matching.lexicon import find_concepts, weak_reasons
from .content import informative_words


@dataclass(frozen=True, slots=True)
class Story:
    """What a sender told the bank about one stopped transfer."""

    receiver_id: str
    text: str
    at: datetime
    case_id: str


def is_similar_story(first: str, second: str) -> bool:
    """Two sender stories are similar in words or name the same people and reason."""
    left, right = informative_words(first), informative_words(second)
    if not left or not right:
        return False
    a, b = find_concepts(first), find_concepts(second)
    own_a, own_b = a.reasons - weak_reasons(), b.reasons - weak_reasons()
    if own_a and own_b and not own_a & own_b:
        return False
    if trigram_cosine(" ".join(left), " ".join(right)) >= config.REPEATED_STORY_SIMILARITY:
        return True
    same_people = bool(a.relations & b.relations) or not (a.relations or b.relations)
    if own_a or own_b:
        return same_people and bool(own_a & own_b)
    return bool(a.relations & b.relations) and bool(a.reasons & b.reasons)


def similar_receivers(stories: tuple[Story, ...], receiver_id: str, text: str, now: datetime) -> int:
    """Count the other receivers with a similar sender story in the window."""
    start = now - config.REPEATED_STORY_WINDOW
    others = {
        story.receiver_id
        for story in stories
        if story.receiver_id != receiver_id and start <= story.at <= now and is_similar_story(story.text, text)
    }
    return len(others)
