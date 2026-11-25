"""Builds the matcher chain from the environment and reports what is active."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .. import config
from .chain import FallbackMatcher
from .deadline import call_with_deadline
from .gemini import GeminiMatcher, make_client
from .gemini_models import ModelState, choose_model, list_flash_names
from .offline import OfflineMatcher
from .types import Matcher

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MatcherStatus:
    """What the start page shows. Never holds the key."""

    active: str  # "gemini" or "offline"
    reason: str = ""  # why offline: forced, no_key, no_package, client_error
    model: str = ""
    model_state: str = ""
    last_failure: str = ""


class MatcherSetup:
    """The matcher chain plus the state of the language model behind it."""

    def __init__(self, gemini: GeminiMatcher | None, client: Any, reason: str) -> None:
        self._chain = FallbackMatcher(gemini, OfflineMatcher(), self._after_comparison)
        self._gemini = gemini
        self._client = client
        self._reason = reason
        self._model_state = ModelState.CHECKING if gemini else None
        self._checking = threading.Lock()

    @property
    def matcher(self) -> Matcher:
        """The matcher the workflow uses."""
        return self._chain

    @property
    def language_model(self) -> GeminiMatcher | None:
        """The language model alone, for the evaluation and the live check."""
        return self._gemini

    def status(self) -> MatcherStatus:
        """A snapshot for the start page and the console."""
        if self._gemini is None:
            return MatcherStatus(active="offline", reason=self._reason)
        return MatcherStatus(
            active="gemini",
            model=self._gemini.model,
            model_state=self._model_state.value if self._model_state else "",
            last_failure=self._chain.last_failure,
        )

    def confirm_model(self) -> None:
        """Ask Google for its model list and switch models if needed."""
        if self._gemini is None or not self._checking.acquire(blocking=False):
            return
        try:
            self._check_list(self._gemini)
        finally:
            self._checking.release()

    def _check_list(self, gemini: GeminiMatcher) -> None:
        try:
            listed = call_with_deadline(
                lambda: list_flash_names(self._client), config.GEMINI_LIST_TIMEOUT_SECONDS
            )
        except Exception as error:
            _LOG.warning("model list failed: %s", type(error).__name__)
            self._model_state = ModelState.UNCONFIRMED
            return
        choice = choose_model(listed, gemini.model)
        gemini.use_model(choice.model)
        self._model_state = choice.state

    def _after_comparison(self, code: str) -> None:
        """Ask for the list again when the first check failed or the model is gone."""
        if code == "model_not_found" or self._model_state is ModelState.UNCONFIRMED:
            self.confirm_model_in_background()

    def confirm_model_in_background(self) -> None:
        """Start the model check without delaying anybody."""
        if self._gemini is not None:
            threading.Thread(target=self.confirm_model, name="model-check", daemon=True).start()


def _offline(reason: str) -> MatcherSetup:
    return MatcherSetup(None, None, reason)


def build_matcher(
    offline: bool,
    env: Mapping[str, str],
    client_factory: Callable[[str], Any] = make_client,
) -> MatcherSetup:
    """Use Gemini when a key and the package are there, else the offline matcher."""
    if offline:
        return _offline("forced")
    key = env.get("GEMINI_API_KEY", "").strip()
    if not key:
        return _offline("no_key")
    try:
        client = client_factory(key)
    except ImportError:
        return _offline("no_package")
    except Exception as error:
        _LOG.error("cannot create the gemini client: %s", type(error).__name__)
        return _offline("client_error")
    model = env.get("GEMINI_MODEL", "").strip() or config.DEFAULT_GEMINI_MODEL
    gemini = GeminiMatcher(client, model.removeprefix("models/"))
    return MatcherSetup(gemini, client, "")
