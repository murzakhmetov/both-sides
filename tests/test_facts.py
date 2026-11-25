"""Risky bank facts and their thresholds."""

from __future__ import annotations

import pytest

from bothsides.decision.facts import BankFacts, RiskyFact, risky_facts

CALM = BankFacts(account_age_days=900, first_time_senders_today=0, earlier_transfers=6)


def test_calm_facts_have_no_risk() -> None:
    assert risky_facts(CALM) == ()


@pytest.mark.parametrize(("age", "risky"), [(0, True), (4, True), (13, True), (14, False), (15, False)])
def test_account_age_threshold(age: int, risky: bool) -> None:
    facts = BankFacts(account_age_days=age, first_time_senders_today=0, earlier_transfers=1)
    assert (RiskyFact.NEW_ACCOUNT in risky_facts(facts)) is risky


@pytest.mark.parametrize(("senders", "risky"), [(0, False), (2, False), (3, True), (5, True)])
def test_first_time_senders_threshold(senders: int, risky: bool) -> None:
    facts = BankFacts(account_age_days=100, first_time_senders_today=senders, earlier_transfers=1)
    assert (RiskyFact.MANY_FIRST_TIME_SENDERS in risky_facts(facts)) is risky


@pytest.mark.parametrize(("count", "risky"), [(0, True), (1, False), (9, False)])
def test_no_earlier_transfers(count: int, risky: bool) -> None:
    facts = BankFacts(account_age_days=100, first_time_senders_today=0, earlier_transfers=count)
    assert (RiskyFact.NO_EARLIER_TRANSFERS in risky_facts(facts)) is risky


def test_sister_story_account_has_all_three() -> None:
    facts = BankFacts(account_age_days=4, first_time_senders_today=5, earlier_transfers=0)
    assert set(risky_facts(facts)) == set(RiskyFact)


@pytest.mark.parametrize(
    "bad",
    [{"account_age_days": -1}, {"first_time_senders_today": -1}, {"earlier_transfers": -1}],
)
def test_negative_numbers_are_rejected(bad: dict[str, int]) -> None:
    values = {"account_age_days": 1, "first_time_senders_today": 1, "earlier_transfers": 1, **bad}
    with pytest.raises(ValueError):
        BankFacts(**values)
