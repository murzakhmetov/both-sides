"""What each screen may see. Phone views are built from an allow-list."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import config
from ..decision.facts import risky_facts
from .model import Case, CaseState, Person, Side
from .transitions import is_deny_armed, is_overdue, is_sender_asked_late

#: The general legal ground shown on phones. Never the reason for this review.
GENERAL_GROUND = "25-1"

_FINAL_WORDS = {
    CaseState.CREDITED: "credited",
    CaseState.WITH_SPECIALIST: "with_specialist",
    CaseState.HELD: "held",
    CaseState.RETURNED: "returned",
}


def _iso(moment: datetime | None) -> str | None:
    return moment.astimezone(config.BANK_TIMEZONE).isoformat(timespec="milliseconds") if moment else None


def _names(person: Person) -> dict[str, str]:
    return {"ru": person.name_ru, "kk": person.name_kk, "en": person.name_en}


def _phone_status(case: Case, side: Side, now: datetime) -> str:
    if side is Side.RECEIVER and case.state is CaseState.WITH_SPECIALIST and case.denied_at:
        return "return_offer"
    if side is Side.SENDER and is_sender_asked_late(case, now):
        return "question"
    if case.state in _FINAL_WORDS:
        return _FINAL_WORDS[case.state]
    asked = CaseState.AWAITING_RECEIVER if side is Side.RECEIVER else CaseState.AWAITING_SENDER
    return "question" if case.state is asked else "waiting"


def _deny_seconds(case: Case, now: datetime) -> float:
    if case.deny_first_tap_at is None or not is_deny_armed(case, now):
        return 0.0
    left = config.DENY_CONFIRM_WINDOW - (now - case.deny_first_tap_at)
    return round(max(left.total_seconds(), 0.0), 3)


def phone_view(case: Case, side: Side, now: datetime) -> dict[str, Any]:
    """The only data a customer phone gets."""
    transfer = case.transfer
    other = transfer.sender if side is Side.RECEIVER else transfer.receiver
    status = _phone_status(case, side, now)
    own_answer = case.receiver_answer if side is Side.RECEIVER else case.sender_answer
    view: dict[str, Any] = {
        "case_id": case.id,
        "case_number": case.id,
        "side": side.value,
        "status": status,
        "answered": own_answer is not None,
        "other_name": _names(other),
        "amount": transfer.amount,
        "answer_by": _iso(case.answer_by) if status == "question" else None,
        "deadline_at": _iso(case.deadline_at) if status in {"held", "with_specialist"} else None,
        "ground": GENERAL_GROUND,
        "objection_sent": any(objection.side is side for objection in case.objections),
    }
    if side is Side.RECEIVER:
        credited = case.state is CaseState.CREDITED
        view["deny_armed_seconds"] = _deny_seconds(case, now)
        view["message"] = transfer.message if credited else None
        view["denied"] = case.denied_at is not None
    return view


def _facts_view(case: Case) -> dict[str, Any]:
    return {
        "account_age_days": case.facts.account_age_days,
        "first_time_senders_today": case.facts.first_time_senders_today,
        "earlier_transfers": case.facts.earlier_transfers,
        "risky": [fact.value for fact in risky_facts(case.facts)],
    }


def _match_view(case: Case) -> dict[str, Any] | None:
    match = case.match
    if match is None:
        return None
    return {
        "probability": match.shown_probability,
        "same_relation": match.same_relation.value,
        "same_reason": match.same_reason.value,
        "note": match.note,
        "source": match.source.value,
        "model": match.model,
        "fallback_code": match.fallback_code,
    }


def _answer_view(case: Case, side: Side) -> dict[str, Any] | None:
    answer = case.receiver_answer if side is Side.RECEIVER else case.sender_answer
    return {"text": answer.text, "at": _iso(answer.at)} if answer else None


def decision_seconds(case: Case) -> float | None:
    """Seconds from the receiver's answer to the decision on the screen, also when a person decided."""
    end = case.closed_at or case.decided_at
    if case.receiver_answer is None or end is None:
        return None
    return round((end - case.receiver_answer.at).total_seconds(), 3)


def case_summary(case: Case, now: datetime) -> dict[str, Any]:
    """One line of the console list. Holds no answers."""
    return {
        "id": case.id,
        "scene": case.scene,
        "state": case.state.value,
        "reasons": [reason.value for reason in case.reasons],
        "risky": [fact.value for fact in risky_facts(case.facts)],
        "amount": case.transfer.amount,
        "sender": _names(case.transfer.sender),
        "receiver": _names(case.transfer.receiver),
        "stopped_at": _iso(case.stopped_at),
        "deadline_at": _iso(case.deadline_at),
        "overdue": is_overdue(case, now),
        "denied": case.denied_at is not None,
        "objections": [objection.side.value for objection in case.objections],
    }


def _thresholds() -> dict[str, float]:
    """The numbers of the config, so that no screen keeps its own copy."""
    return {
        "release": config.RELEASE_PROBABILITY,
        "hold": config.HOLD_PROBABILITY,
        "repeated_story": config.REPEATED_STORY_RECEIVERS,
    }


def case_file(case: Case, now: datetime) -> dict[str, Any]:
    """The full file for a bank specialist."""
    return {
        **case_summary(case, now),
        "thresholds": _thresholds(),
        "transfer": {
            "amount": case.transfer.amount,
            "message": case.transfer.message,
            "sender": _names(case.transfer.sender),
            "receiver": _names(case.transfer.receiver),
        },
        "facts": _facts_view(case),
        "match": _match_view(case),
        "similar_receivers": case.similar_receivers,
        "receiver_answer": _answer_view(case, Side.RECEIVER),
        "sender_answer": _answer_view(case, Side.SENDER),
        "answer_by": _iso(case.answer_by),
        "decided_at": _iso(case.decided_at),
        "closed_at": _iso(case.closed_at),
        "seconds": decision_seconds(case),
        "objections": [{"side": o.side.value, "at": _iso(o.at)} for o in case.objections],
        "trail": [
            {"at": _iso(e.at), "actor": e.actor.value, "event": e.event, "details": list(e.details)}
            for e in case.trail
        ],
    }


def stage_view(case: Case, now: datetime) -> dict[str, Any]:
    """The big screen: both phones, the match, the facts, the decision, the seconds."""
    answer = case.receiver_answer
    running = case.decided_at is None and answer is not None
    elapsed = round((now - answer.at).total_seconds(), 3) if running and answer else None
    return {
        "scene": case.scene,
        "case": case_file(case, now),
        "phones": {side.value: _phone_status(case, side, now) for side in Side},
        "seconds": decision_seconds(case),
        "running_seconds": elapsed,
    }
