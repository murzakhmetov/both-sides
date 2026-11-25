"""Reason codes. Staff see them; customer phones never do."""

from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    """Why a case was not released at once."""

    CLEAR_MISMATCH = "clear_mismatch"
    LOW_MATCH = "low_match"
    TOO_VAGUE = "too_vague"
    REASON_NOT_CONFIRMED = "reason_not_confirmed"
    NO_SHARED_REASON = "no_shared_reason"
    RISKY_FACTS = "risky_facts"
    REPEATED_STORY = "repeated_story"
    RECEIVER_DENIED = "receiver_denied"
    DENIAL_IN_TEXT = "denial_in_text"
    COACHED_IN_TEXT = "coached_in_text"
    NO_ANSWER = "no_answer"
    MATCHER_UNAVAILABLE = "matcher_unavailable"
