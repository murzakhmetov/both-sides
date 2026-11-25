"""Choosing the model, the fallback chain, and what the start page reports."""

from __future__ import annotations

import pytest

from bothsides.matching.chain import FallbackMatcher
from bothsides.matching.factory import build_matcher
from bothsides.matching.gemini_models import ModelState, choose_model
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.types import MatcherError, MatchSource

from .fakes import FakeGeminiClient, StubMatcher, gemini_reply, gemini_result

KEY = "unit-test-key-value"


@pytest.mark.parametrize(
    ("listed", "wanted", "model", "state"),
    [
        (["gemini-3.8-flash", "gemini-3.6-flash"], "gemini-3.8-flash", "gemini-3.8-flash", ModelState.CONFIRMED),
        (["gemini-3.6-flash", "gemini-3.5-flash-lite"], "gemini-3.8-flash", "gemini-3.6-flash", ModelState.REPLACED),
        (["gemini-3.10-flash", "gemini-3.9-flash"], "gemini-1-flash", "gemini-3.10-flash", ModelState.REPLACED),
        (["gemini-4-flash", "gemini-3.9-flash"], "gemini-1-flash", "gemini-4-flash", ModelState.REPLACED),
        (["gemini-3.5-flash-lite"], "gemini-3.8-flash", "gemini-3.5-flash-lite", ModelState.REPLACED),
        (["gemini-3-flash-preview"], "gemini-3-flash-preview", "gemini-3-flash-preview", ModelState.CONFIRMED),
        (["gemini-3.8-flash-tts", "gemini-3.1-flash-image"], "gemini-3.8-flash", "gemini-3.8-flash", ModelState.UNCONFIRMED),
        ([], "gemini-3.8-flash", "gemini-3.8-flash", ModelState.UNCONFIRMED),
    ],
)
def test_choose_model(listed: list[str], wanted: str, model: str, state: ModelState) -> None:
    choice = choose_model(listed, wanted)
    assert (choice.model, choice.state) == (model, state)


def test_chain_prefers_the_language_model() -> None:
    chain = FallbackMatcher(StubMatcher(gemini_result(0.9)), OfflineMatcher())
    assert chain.compare("брат аренда", "брату аренда").source is MatchSource.GEMINI


@pytest.mark.parametrize("error", [MatcherError("timeout"), MatcherError("invalid_json"), RuntimeError("boom")])
def test_chain_falls_back_to_the_offline_matcher(error: Exception) -> None:
    chain = FallbackMatcher(StubMatcher(error), OfflineMatcher())
    result = chain.compare("брат аренда", "брату аренда")
    assert result.source is MatchSource.OFFLINE
    assert result.fallback_code == (error.code if isinstance(error, MatcherError) else "error")


def test_chain_without_a_language_model() -> None:
    result = FallbackMatcher(None, OfflineMatcher()).compare("брат аренда", "брату аренда")
    assert result.source is MatchSource.OFFLINE
    assert result.fallback_code == ""


def test_chain_when_nobody_answers() -> None:
    chain = FallbackMatcher(StubMatcher(MatcherError("timeout")), StubMatcher(RuntimeError("boom")))
    with pytest.raises(MatcherError) as caught:
        chain.compare("брат аренда", "брату аренда")
    assert caught.value.code == "no_matcher"


def test_missing_key_runs_offline() -> None:
    setup = build_matcher(offline=False, env={})
    status = setup.status()
    assert (status.active, status.reason) == ("offline", "no_key")
    assert setup.matcher.compare("брат аренда", "брату аренда").source is MatchSource.OFFLINE


def test_blank_key_counts_as_missing() -> None:
    assert build_matcher(offline=False, env={"GEMINI_API_KEY": "   "}).status().reason == "no_key"


def test_forced_offline_ignores_the_key() -> None:
    def forbidden(key: str) -> object:
        raise AssertionError("no client may be created offline")

    setup = build_matcher(offline=True, env={"GEMINI_API_KEY": KEY}, client_factory=forbidden)
    assert (setup.status().active, setup.status().reason) == ("offline", "forced")


def test_missing_package_runs_offline() -> None:
    def missing(key: str) -> object:
        raise ImportError("google.genai")

    setup = build_matcher(offline=False, env={"GEMINI_API_KEY": KEY}, client_factory=missing)
    assert (setup.status().active, setup.status().reason) == ("offline", "no_package")


def test_key_gives_the_language_model() -> None:
    client = FakeGeminiClient(gemini_reply(probability=0.88), models=["gemini-3.8-flash"])
    setup = build_matcher(offline=False, env={"GEMINI_API_KEY": KEY}, client_factory=lambda key: client)
    setup.confirm_model()
    status = setup.status()
    assert (status.active, status.model, status.model_state) == ("gemini", "gemini-3.8-flash", "confirmed")
    assert setup.matcher.compare("брат аренда", "брату аренда").source is MatchSource.GEMINI


def test_model_from_the_environment_is_replaced_when_not_listed() -> None:
    client = FakeGeminiClient(gemini_reply(), models=["gemini-3.6-flash"])
    env = {"GEMINI_API_KEY": KEY, "GEMINI_MODEL": "gemini-9-flash"}
    setup = build_matcher(offline=False, env=env, client_factory=lambda key: client)
    assert setup.status().model == "gemini-9-flash"
    setup.confirm_model()
    assert (setup.status().model, setup.status().model_state) == ("gemini-3.6-flash", "replaced")
    setup.matcher.compare("брат аренда", "брату аренда")
    assert client.interactions.calls[0]["model"] == "gemini-3.6-flash"


def test_failed_model_list_keeps_the_wanted_model() -> None:
    client = FakeGeminiClient(gemini_reply(), models=RuntimeError("network down"))
    setup = build_matcher(offline=False, env={"GEMINI_API_KEY": KEY}, client_factory=lambda key: client)
    setup.confirm_model()
    assert (setup.status().model, setup.status().model_state) == ("gemini-3.8-flash", "unconfirmed")


def test_key_never_shows_in_status_or_repr() -> None:
    client = FakeGeminiClient(gemini_reply())
    setup = build_matcher(offline=False, env={"GEMINI_API_KEY": KEY}, client_factory=lambda key: client)
    setup.confirm_model()
    for text in (repr(setup), repr(setup.status()), repr(setup.matcher), str(vars(setup.status()) if hasattr(setup.status(), "__dict__") else setup.status())):
        assert KEY not in text


def test_last_failure_is_reported_to_staff() -> None:
    client = FakeGeminiClient(RuntimeError("boom"))
    setup = build_matcher(offline=False, env={"GEMINI_API_KEY": KEY}, client_factory=lambda key: client)
    assert setup.status().last_failure == ""
    setup.matcher.compare("брат аренда", "брату аренда")
    assert setup.status().last_failure == "error"
