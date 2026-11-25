"""The mini-demo of the landing page: the offline matcher and the rules, nothing else.

No language model, no network, nothing stored. Bank facts count as calm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.gate import GateInput, Outcome, decide
from ..decision.reasons import ReasonCode
from ..matching.denials import DenialKind, find_denial
from ..matching.offline import OfflineMatcher
from .service import clean_answer

_TYPED_REASONS = {
    DenialKind.DENIAL: ReasonCode.DENIAL_IN_TEXT,
    DenialKind.COACHED: ReasonCode.COACHED_IN_TEXT,
}


@dataclass(frozen=True, slots=True)
class TryResult:
    """What the app would do with these two answers."""

    released: bool
    reasons: tuple[ReasonCode, ...] = ()

    def view(self) -> dict[str, Any]:
        """The JSON of the landing page."""
        return {
            "result": "match" if self.released else "specialist",
            "reasons": [reason.value for reason in self.reasons],
        }


def try_answers(receiver_text: str, sender_text: str) -> TryResult:
    """Give the verdict of the offline matcher for two typed answers."""
    receiver, sender = clean_answer(receiver_text), clean_answer(sender_text)
    denials = (find_denial(receiver), find_denial(sender))
    typed = tuple(dict.fromkeys(_TYPED_REASONS[kind] for kind in denials if kind))
    if typed:
        return TryResult(False, typed)
    match = OfflineMatcher().compare(receiver, sender)
    decision = decide(GateInput(match, receiver, sender, risky_facts=0, similar_receivers=0))
    return TryResult(decision.outcome is Outcome.RELEASE, decision.reasons)
