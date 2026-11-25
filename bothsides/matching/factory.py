"""Builds the matcher chain from the environment and reports what is active."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .. import config
from .chain import FallbackMatcher
from .deadline import call_with_deadline
from .gemini import GeminiMatcher, make_client
from .gemini_models import ModelState, choose_model, list_flash_names, spare_models
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
        self._check_after = 0.0

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

    def confirm_model(self, seconds: float = config.GEMINI_LIST_TIMEOUT_SECONDS) -> None:
        """Ask Google for its model list and switch models if needed."""
        if self._gemini is None or not self._checking.acquire(blocking=False):
            return
        try:
            self._check_list(self._gemini, seconds)
        finally:
            self._checking.release()

    def _check_list(self, gemini: GeminiMatcher, seconds: float) -> None:
        try:
            listed = call_with_deadline(lambda: list_flash_names(self._client), seconds)
        except Exception as error:
            _LOG.warning("model list failed: %s", type(error).__name__)
            self._model_state = ModelState.UNCONFIRMED
            return
        choice = choose_model(listed, gemini.model)
        gemini.use_model(choice.model, spare_models(listed, choice.model, config.GEMINI_SPARE_MODELS))
        self._model_state = choice.state

    def _after_comparison(self, code: str) -> None:
        """Ask for the list again when the first check failed or the model is gone."""
        if code == "model_not_found" or self._model_state is ModelState.UNCONFIRMED:
            self.confirm_model_in_background()

    def confirm_model_in_background(self) -> None:
        """Start the model check without delaying anybody."""
        if self._gemini is not None:
            threading.Thread(target=self._prepare, name="model-check", daemon=True).start()

    def confirm_model_now(self) -> None:
        """The check within a request, for a host that stops threads between requests.

        After a failure it is made again, but not at every request.
        """
        open_ = self._model_state in (ModelState.CHECKING, ModelState.UNCONFIRMED)
        if open_ and time.monotonic() >= self._check_after:
            self._check_after = time.monotonic() + config.GEMINI_CHECK_AGAIN_SECONDS
            self._prepare(config.ONLINE_LIST_TIMEOUT_SECONDS)

    def _prepare(self, seconds: float = config.GEMINI_LIST_TIMEOUT_SECONDS) -> None:
        if self._gemini is None:
            return
        try:
            self._gemini.warm_up()
        except Exception as error:
            _LOG.warning("gemini client failed: %s", type(error).__name__)
            self._model_state = ModelState.UNCONFIRMED
            return
        self.confirm_model(seconds)


def _offline(reason: str) -> MatcherSetup:
    return MatcherSetup(None, None, reason)


def build_matcher(
    offline: bool,
    env: Mapping[str, str],
    client_factory: Callable[[str], Any] = make_client,
    may_ask: Callable[[], bool] = lambda: True,
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
    gemini = GeminiMatcher(client, model.removeprefix("models/"), may_ask=may_ask)
    gemini.use_model(gemini.model, tuple(name for name in config.GEMINI_SPARE_MODELS if name != gemini.model))
    return MatcherSetup(gemini, client, "")
