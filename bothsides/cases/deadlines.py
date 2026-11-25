"""Working-day deadlines of article 25-1 (five working days)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .. import config


def is_working_day(day: date) -> bool:
    """True for Monday to Friday unless it is a public holiday."""
    return day.weekday() < 5 and day not in config.PUBLIC_HOLIDAYS


def add_working_days(day: date, count: int) -> date:
    """Return the date that is *count* working days after *day*."""
    if count < 0:
        raise ValueError("count must not be negative")
    current = day
    remaining = count
    while remaining > 0:
        current += timedelta(days=1)
        if is_working_day(current):
            remaining -= 1
    return current


def hold_deadline(stopped_at: datetime) -> datetime:
    """Return the end of the fifth working day after the transfer was stopped.

    The day of the stop is day 0, as the law counts "from the date of
    suspension". The time is the end of the bank's working day.
    """
    if stopped_at.tzinfo is None:
        raise ValueError("stopped_at needs a time zone")
    local = stopped_at.astimezone(config.BANK_TIMEZONE)
    last_day = add_working_days(local.date(), config.HOLD_WORKING_DAYS)
    return datetime.combine(last_day, config.HOLD_DEADLINE_TIME, tzinfo=config.BANK_TIMEZONE)
