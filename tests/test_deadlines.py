"""Working-day deadlines: weekends, the 16 December holiday and year end."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from bothsides.cases.deadlines import add_working_days, hold_deadline, is_working_day
from bothsides.config import BANK_TIMEZONE


def at(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=BANK_TIMEZONE)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 27), True),  # Friday
        (date(2026, 11, 28), False),  # Saturday
        (date(2026, 11, 29), False),  # Sunday
        (date(2026, 12, 16), False),  # Independence Day, Wednesday
        (date(2026, 12, 17), True),  # an ordinary Thursday now
        (date(2027, 1, 1), False),
        (date(2027, 1, 4), False),  # moved from Saturday 2 January
    ],
)
def test_is_working_day(day: date, expected: bool) -> None:
    assert is_working_day(day) is expected


def test_semifinal_day_deadline() -> None:
    # Thursday 26 November: 27, 30, 1, 2, 3 December.
    assert hold_deadline(at(2026, 11, 26)).date() == date(2026, 12, 3)


def test_demo_day_deadline_skips_the_holiday() -> None:
    # Friday 11 December: 14, 15, (16 is a holiday), 17, 18, 21 December.
    assert hold_deadline(at(2026, 12, 11)).date() == date(2026, 12, 21)


def test_transfer_stopped_on_saturday_counts_from_monday() -> None:
    assert hold_deadline(at(2026, 11, 28)).date() == date(2026, 12, 4)


def test_deadline_is_end_of_the_bank_day_in_bank_time() -> None:
    deadline = hold_deadline(at(2026, 11, 26, 23))
    assert (deadline.hour, deadline.minute) == (18, 0)
    assert deadline.utcoffset() == BANK_TIMEZONE.utcoffset(None)


def test_stop_time_in_another_zone_uses_the_bank_date() -> None:
    # 20:30 UTC on Thursday is already Friday in Kazakhstan (UTC+5).
    stopped = datetime(2026, 11, 26, 20, 30, tzinfo=timezone.utc)
    assert hold_deadline(stopped).date() == date(2026, 12, 4)


def test_naive_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        hold_deadline(datetime(2026, 11, 26, 12))


def test_add_working_days_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        add_working_days(date(2026, 11, 26), -1)


def test_year_end_run() -> None:
    # Tuesday 29 December 2026: 30, 31, (1 and 4 January off), 5, 6, (7 off), 8.
    assert add_working_days(date(2026, 12, 29), 5) == date(2027, 1, 8)
