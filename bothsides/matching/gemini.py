"""Gemini adapter: one structured-output request through the Interactions API.

Call shape checked on 24 November 2026 against the structured-outputs page of
the Gemini API docs and the google-genai 3.6.1 source. ``store=False`` keeps the
answers out of Google's server-side interaction storage.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from .. import config
from ..textnorm import one_line
from .deadline import DeadlineExceeded, call_with_deadline
from .gemini_prompt import RESPONSE_SCHEMA, SYSTEM_INSTRUCTION, build_input
from .redact import redact
from .types import MatcherError, MatchResult, MatchSource, Tri

_LOG = logging.getLogger(__name__)

#: SDK error classes by name, so that this module needs no SDK import.
_ERROR_CODES = {
    "APITimeoutError": "timeout",
    "AuthenticationError": "auth",
    "PermissionDeniedError": "auth",
    "RateLimitError": "rate_limited",
    "NotFoundError": "model_not_found",
    "APIConnectionError": "connection",
}


def make_client(api_key: str, http_client: Any = None) -> Any:
    """Create the SDK client. The key is passed explicitly, never logged."""
    from google import genai
    from google.genai import types

    options = types.HttpOptions(
        timeout=int(config.GEMINI_TIMEOUT_SECONDS * 1000),
        retry_options=types.HttpRetryOptions(attempts=config.GEMINI_ATTEMPTS),
        httpx_client=http_client,
    )
    return genai.Client(api_key=api_key, http_options=options)


def _reject_constant(_: str) -> float:
    raise ValueError("NaN and Infinity are not valid JSON")


def _read_probability(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("probability is not a number")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("probability is out of range")
    return number


def _read_tri(value: Any) -> Tri:
    if not isinstance(value, str):
        raise ValueError("expected true, false or unknown")
    return Tri(value)


def _read_note(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("note is not text")
    return one_line(value)[: config.MAX_NOTE_LENGTH]


def parse_reply(text: str, model: str) -> MatchResult:
    """Validate the model's JSON. Raises MatcherError("invalid_json")."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return MatchResult(
            probability=_read_probability(data["probability"]),
            same_relation=_read_tri(data["same_relation"]),
            same_reason=_read_tri(data["same_reason"]),
            note=_read_note(data["note"]),
            source=MatchSource.GEMINI,
            model=model,
        )
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
        raise MatcherError("invalid_json") from None


class GeminiMatcher:
    """Asks Gemini once. Any problem becomes a :class:`MatcherError`."""

    def __init__(
        self, client: Any, model: str, timeout_seconds: float = config.GEMINI_TIMEOUT_SECONDS
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    @property
    def model(self) -> str:
        """The model used for the next request."""
        return self._model

    def use_model(self, model: str) -> None:
        """Switch to another model, for example when the wanted one is gone."""
        self._model = model

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        receiver = redact(receiver_text[: config.MAX_ANSWER_LENGTH])
        sender = redact(sender_text[: config.MAX_ANSWER_LENGTH])
        if not receiver or not sender:
            raise MatcherError("empty")
        model = self._model
        interaction = self._ask(model, build_input(receiver, sender))
        if getattr(interaction, "status", None) != "completed":
            raise MatcherError("incomplete")
        text = getattr(interaction, "output_text", None)
        if not text and text != "":
            raise MatcherError("empty_reply")
        return parse_reply(text, model)

    def _request(self, model: str, text: str) -> dict[str, Any]:
        return {
            "model": model,
            "input": text,
            "system_instruction": SYSTEM_INSTRUCTION,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": RESPONSE_SCHEMA,
            },
            "generation_config": {
                "thinking_level": config.GEMINI_THINKING_LEVEL,
                "max_output_tokens": config.GEMINI_MAX_OUTPUT_TOKENS,
            },
            "store": False,
            "timeout": self._timeout,
            "automatic_continuation": False,
        }

    def _ask(self, model: str, text: str) -> Any:
        request = self._request(model, text)
        try:
            return call_with_deadline(lambda: self._client.interactions.create(**request), self._timeout)
        except DeadlineExceeded:
            code = "timeout"
        except Exception as error:
            # Only the class name is logged: messages may hold request details.
            name = type(error).__name__
            code = _ERROR_CODES.get(name, "error")
            _LOG.warning("gemini request failed: %s", name)
        raise MatcherError(code)
