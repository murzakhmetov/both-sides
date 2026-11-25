"""The repeated-story check over the last 30 days."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from bothsides.config import BANK_TIMEZONE
from bothsides.decision.stories import Story, is_similar_story, similar_receivers

NOW = datetime(2026, 11, 26, 12, tzinfo=BANK_TIMEZONE)


def story(receiver: str, text: str, days_ago: float = 1, case_id: str = "") -> Story:
    return Story(receiver_id=receiver, text=text, at=NOW - timedelta(days=days_ago), case_id=case_id or receiver)


def count(stories: list[Story], text: str = "сестре на лечение", receiver: str = "me") -> int:
    return similar_receivers(tuple(stories), receiver, text, NOW)


def test_no_history() -> None:
    assert count([]) == 0


def test_counts_distinct_other_receivers() -> None:
    stories = [story("a", "сестре на лечение"), story("a", "сестре на лечение", 2), story("b", "на лечение сестре")]
    assert count(stories) == 2


def test_own_history_does_not_count() -> None:
    assert count([story("me", "сестре на лечение", case_id="x"), story("me", "сестре на лечение", 3)]) == 0


@pytest.mark.parametrize(("days", "expected"), [(0.1, 1), (29.9, 1), (30.1, 0), (90, 0)])
def test_window_is_thirty_days(days: float, expected: int) -> None:
    assert count([story("a", "сестре на лечение", days)]) == expected


def test_future_stories_do_not_count() -> None:
    assert count([story("a", "сестре на лечение", -1)]) == 0


@pytest.mark.parametrize(
    ("first", "second", "similar"),
    [
        ("сестре на лечение", "Сестре на лечение!", True),
        ("сестре на лечение", "для сестры, лечение", True),
        ("сестре на лечение", "сіңліме емге", True),
        ("сестре на лечение", "брату за аренду", False),
        ("сестре на лечение", "сестре на учебу", False),
        ("ok", "ok", False),
        ("", "", False),
        ("спасибо большое", "спасибо большое", False),
    ],
)
def test_similarity(first: str, second: str, similar: bool) -> None:
    assert is_similar_story(first, second) is similar
    assert is_similar_story(second, first) is similar
