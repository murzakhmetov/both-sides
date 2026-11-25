"""Risky bank facts about the receiver. Seeded in the demo."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum

from .. import config


class RiskyFact(str, Enum):
    """A bank fact that counts as risky."""

    NEW_ACCOUNT = "new_account"
    MANY_FIRST_TIME_SENDERS = "many_first_time_senders"
    NO_EARLIER_TRANSFERS = "no_earlier_transfers"


@dataclass(frozen=True, slots=True)
class BankFacts:
    """What the bank already knows about the receiver and the pair."""

    account_age_days: int
    first_time_senders_today: int
    earlier_transfers: int

    def __post_init__(self) -> None:
        for field in fields(self):
            if getattr(self, field.name) < 0:
                raise ValueError(f"{field.name} must not be negative")


def risky_facts(facts: BankFacts) -> tuple[RiskyFact, ...]:
    """Return the risky facts in a fixed order."""
    checks = (
        (RiskyFact.NEW_ACCOUNT, facts.account_age_days < config.NEW_ACCOUNT_DAYS),
        (
            RiskyFact.MANY_FIRST_TIME_SENDERS,
            facts.first_time_senders_today >= config.MANY_FIRST_TIME_SENDERS,
        ),
        (RiskyFact.NO_EARLIER_TRANSFERS, facts.earlier_transfers == 0),
    )
    return tuple(fact for fact, present in checks if present)
