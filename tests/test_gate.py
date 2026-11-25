"""The release gate: every condition alone can stop a release."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bothsides.decision.gate import GateInput, Outcome, decide
from bothsides.decision.reasons import ReasonCode
from bothsides.matching.types import MatchResult, MatchSource, Tri

RECEIVER = "ағам пәтер жалдау ақысының жартысын жіберді"
SENDER = "Брату, моя половина аренды квартиры"


def match(
    probability: float = 0.95,
    source: MatchSource = MatchSource.GEMINI,
    same_reason: Tri = Tri.TRUE,
) -> MatchResult:
    return MatchResult(
        probability=probability, same_relation=Tri.TRUE, same_reason=same_reason, note="", source=source
    )


def gate(**changes: object) -> GateInput:
    base = GateInput(
        match=match(), receiver_text=RECEIVER, sender_text=SENDER, risky_facts=0, similar_receivers=0
    )
    return replace(base, **changes)


@pytest.mark.parametrize("source", list(MatchSource))
def test_release_when_everything_holds(source: MatchSource) -> None:
    decision = decide(gate(match=match(source=source)))
    assert decision.outcome is Outcome.RELEASE
    assert decision.reasons == ()


@pytest.mark.parametrize(
    ("probability", "outcome"),
    [
        (1.0, Outcome.RELEASE),
        (0.80, Outcome.RELEASE),
        (0.7999, Outcome.PERSON),
        (0.35, Outcome.PERSON),
        (0.3499, Outcome.HOLD),
        (0.0, Outcome.HOLD),
    ],
)
def test_probability_thresholds_for_the_language_model(probability: float, outcome: Outcome) -> None:
    same_reason = Tri.TRUE if probability >= 0.8 else Tri.FALSE
    assert decide(gate(match=match(probability, same_reason=same_reason))).outcome is outcome


@pytest.mark.parametrize("probability", [0.0, 0.1, 0.34, 0.35, 0.5, 0.79])
def test_offline_matcher_never_holds(probability: float) -> None:
    decision = decide(gate(match=match(probability, MatchSource.OFFLINE, Tri.FALSE)))
    assert decision.outcome is Outcome.PERSON


@pytest.mark.parametrize("same_reason", [Tri.FALSE, Tri.UNKNOWN])
@pytest.mark.parametrize("source", list(MatchSource))
def test_high_probability_without_the_same_reason_goes_to_a_person(
    same_reason: Tri, source: MatchSource
) -> None:
    decision = decide(gate(match=match(0.99, source, same_reason)))
    assert decision.outcome is Outcome.PERSON
    expected = (
        ReasonCode.REASON_NOT_CONFIRMED if source is MatchSource.GEMINI else ReasonCode.NO_SHARED_REASON
    )
    assert expected in decision.reasons


@pytest.mark.parametrize("field", ["receiver_text", "sender_text"])
@pytest.mark.parametrize("text", ["ok", "спасибо большое", "долг"])
def test_vague_answer_goes_to_a_person_never_release(field: str, text: str) -> None:
    decision = decide(gate(**{field: text}))
    assert decision.outcome is Outcome.PERSON
    assert ReasonCode.TOO_VAGUE in decision.reasons


@pytest.mark.parametrize("field", ["receiver_text", "sender_text"])
def test_vague_answer_is_never_held(field: str) -> None:
    decision = decide(gate(match=match(0.01, same_reason=Tri.FALSE), **{field: "спасибо большое"}))
    assert decision.outcome is Outcome.PERSON


def test_unknown_reason_is_never_held() -> None:
    # Nonsense and greetings come back as "unknown": they go to a person.
    decision = decide(
        gate(
            match=match(0.01, same_reason=Tri.UNKNOWN),
            receiver_text="синий трактор едет",
            sender_text="зелёный чайник поёт",
        )
    )
    assert decision.outcome is Outcome.PERSON


@pytest.mark.parametrize(
    ("risky", "outcome"),
    [(0, Outcome.RELEASE), (1, Outcome.RELEASE), (2, Outcome.PERSON), (3, Outcome.PERSON)],
)
def test_risky_facts_limit(risky: int, outcome: Outcome) -> None:
    decision = decide(gate(risky_facts=risky))
    assert decision.outcome is outcome
    assert (ReasonCode.RISKY_FACTS in decision.reasons) is (risky >= 2)


@pytest.mark.parametrize(
    ("others", "outcome"),
    [(0, Outcome.RELEASE), (1, Outcome.RELEASE), (2, Outcome.PERSON), (7, Outcome.PERSON)],
)
def test_repeated_story_limit(others: int, outcome: Outcome) -> None:
    decision = decide(gate(similar_receivers=others))
    assert decision.outcome is outcome
    assert (ReasonCode.REPEATED_STORY in decision.reasons) is (others >= 2)


def test_no_matcher_answer_goes_to_a_person() -> None:
    decision = decide(gate(match=None))
    assert decision.outcome is Outcome.PERSON
    assert decision.reasons == (ReasonCode.MATCHER_UNAVAILABLE,)


def test_clear_mismatch_is_the_first_reason_of_a_hold() -> None:
    decision = decide(gate(match=match(0.02, same_reason=Tri.FALSE), risky_facts=3))
    assert decision.outcome is Outcome.HOLD
    assert decision.reasons[0] is ReasonCode.CLEAR_MISMATCH
    assert ReasonCode.RISKY_FACTS in decision.reasons


def test_every_non_release_names_a_reason() -> None:
    for probability in (0.0, 0.2, 0.5, 0.79):
        for source in MatchSource:
            decision = decide(gate(match=match(probability, source, Tri.FALSE)))
            assert decision.reasons
