"""Gemini adapter: one structured-output request through the Interactions API.

Call shape checked on 24 November 2026 against the structured-outputs page of
the Gemini API docs and the google-genai 3.6.1 source. ``store=False`` keeps the
answers out of Google's server-side interaction storage.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Callable

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
    "InternalServerError": "server_error",
}

#: After these another model may still answer; after the others one more try changes nothing.
_NEXT_MODEL = frozenset({"server_error", "rate_limited", "model_not_found", "timeout"})


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
    """Asks Gemini, and spare models while the first one is overloaded. Problems become :class:`MatcherError`."""

    def __init__(
        self,
        client: Any,
        model: str,
        timeout_seconds: float = config.GEMINI_TIMEOUT_SECONDS,
        may_ask: Callable[[], bool] = lambda: True,
    ) -> None:
        """*may_ask* is heard before each request: False keeps a public page within its budget."""
        self._client = client
        self._model = model
        self._spares: tuple[str, ...] = ()
        self._answered = ("", 0.0)
        self._timeout = timeout_seconds
        self._may_ask = may_ask

    @property
    def model(self) -> str:
        """The model used for the next request."""
        return self._model

    def use_model(self, model: str, spares: tuple[str, ...] = ()) -> None:
        """Switch to another model, for example when the wanted one is gone. *spares* get the next tries."""
        self._model = model
        self._spares = spares

    def warm_up(self) -> None:
        """Let the SDK load its modules, which takes seconds on a small machine, before any clock runs."""
        getattr(self._client, "interactions", None)

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        receiver = redact(receiver_text[: config.MAX_ANSWER_LENGTH])
        sender = redact(sender_text[: config.MAX_ANSWER_LENGTH])
        if not receiver or not sender:
            raise MatcherError("empty")
        if not self._may_ask():
            raise MatcherError("rate_limited")
        text = build_input(receiver, sender)
        self.warm_up()
        until = time.monotonic() + self._timeout
        *others, last = self._order()
        for model in others:
            try:
                return self._once(model, text, min(config.GEMINI_TRY_SECONDS, until - time.monotonic()))
            except MatcherError as error:
                # The main model is gone: the caller has to hear it and ask for the list again.
                gone = error.code == "model_not_found" and model == self._model
                if gone or error.code not in _NEXT_MODEL or until - time.monotonic() < config.GEMINI_NEXT_TRY_SECONDS:
                    raise
        return self._once(last, text, until - time.monotonic())

    def _order(self) -> tuple[str, ...]:
        """The models to ask. The one that answered a moment ago comes first."""
        models = (self._model, *self._spares)
        first, until = self._answered
        if first not in models or time.monotonic() > until:
            return models
        return (first, *(model for model in models if model != first))

    def _once(self, model: str, text: str, seconds: float) -> MatchResult:
        interaction = self._ask(model, text, seconds)
        if getattr(interaction, "status", None) != "completed":
            raise MatcherError("incomplete")
        reply = getattr(interaction, "output_text", None)
        if not reply and reply != "":
            raise MatcherError("empty_reply")
        result = parse_reply(reply, model)
        self._answered = (model, time.monotonic() + config.GEMINI_KEEP_SECONDS)
        return result

    def _request(self, model: str, text: str, seconds: float) -> dict[str, Any]:
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
            "timeout": seconds,
            "automatic_continuation": False,
        }

    def _ask(self, model: str, text: str, seconds: float) -> Any:
        request = self._request(model, text, seconds)
        try:
            return call_with_deadline(lambda: self._client.interactions.create(**request), seconds)
        except DeadlineExceeded:
            code = "timeout"
        except Exception as error:
            # Only the class name and the HTTP status are logged: messages may hold request details.
            name = type(error).__name__
            code = _ERROR_CODES.get(name, "error")
            status = getattr(error, "status_code", None)
            _LOG.warning("gemini request failed: %s %s %s", model, name, status if isinstance(status, int) else "")
        raise MatcherError(code)
