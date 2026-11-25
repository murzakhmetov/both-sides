"""Language model first, offline matcher second, a person if both fail."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable

from .types import Matcher, MatcherError, MatchResult

_LOG = logging.getLogger(__name__)


class FallbackMatcher:
    """Tries the primary matcher and falls back to the second one."""

    def __init__(
        self,
        primary: Matcher | None,
        fallback: Matcher,
        on_primary: Callable[[str], None] = lambda code: None,
    ) -> None:
        """*on_primary* hears after each try of the primary matcher how it went:
        an empty code or the code of the failure."""
        self._primary = primary
        self._fallback = fallback
        self._on_primary = on_primary
        self._last_failure = ""

    @property
    def last_failure(self) -> str:
        """Code of the latest problem with the primary matcher, for staff."""
        return self._last_failure

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        code = ""
        if self._primary is not None:
            try:
                result = self._primary.compare(receiver_text, sender_text)
            except MatcherError as error:
                if error.code == "empty":
                    # Nothing is left to compare. The raw text must not reach
                    # the word list instead: a person reads it.
                    raise
                code = error.code
            except Exception as error:
                code = "error"
                _LOG.error("matcher failed: %s", type(error).__name__)
            else:
                self._note("")
                return result
            self._note(code)
        try:
            return replace(self._fallback.compare(receiver_text, sender_text), fallback_code=code)
        except Exception as error:
            _LOG.error("fallback matcher failed: %s", type(error).__name__)
            raise MatcherError("no_matcher") from None

    def _note(self, code: str) -> None:
        self._last_failure = code
        self._on_primary(code)
