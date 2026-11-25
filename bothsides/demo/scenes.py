"""The three demo scenes. All people and amounts are invented."""

from __future__ import annotations

from dataclasses import dataclass

from ..cases.model import Person, Transfer
from ..decision.facts import BankFacts


@dataclass(frozen=True, slots=True)
class Scene:
    """One prepared story with the texts the presenter types."""

    id: str
    transfer: Transfer
    facts: BankFacts
    receiver_script: str
    sender_script: str


SCENES: tuple[Scene, ...] = (
    Scene(
        id="brother",
        transfer=Transfer(
            sender=Person("client-101", "Ерлан", "Ерлан", "Yerlan"),
            receiver=Person("client-102", "Арман", "Арман", "Arman"),
            amount=90_000,
            message="за квартиру",
        ),
        facts=BankFacts(account_age_days=1_460, first_time_senders_today=0, earlier_transfers=11),
        receiver_script="ағам пәтер жалдау ақысының жартысын жіберді",
        sender_script="Брату, моя половина аренды квартиры",
    ),
    Scene(
        id="sister",
        transfer=Transfer(
            sender=Person("client-201", "Гульнар", "Гүлнар", "Gulnar"),
            receiver=Person("client-202", "Тимур", "Тимур", "Timur"),
            amount=450_000,
            message="на лечение",
        ),
        facts=BankFacts(account_age_days=4, first_time_senders_today=5, earlier_transfers=0),
        receiver_script="друг вернул долг",
        sender_script="сестре на лечение",
    ),
    Scene(
        id="stranger",
        transfer=Transfer(
            sender=Person("client-301", "Сауле", "Сәуле", "Saule"),
            receiver=Person("client-302", "Марат", "Марат", "Marat"),
            amount=120_000,
            message="как договорились",
        ),
        facts=BankFacts(account_age_days=730, first_time_senders_today=1, earlier_transfers=0),
        receiver_script="",
        sender_script="оплата за товар с сайта",
    ),
)
