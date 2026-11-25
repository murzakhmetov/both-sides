"""What a public page may spend on the language model, and how the models share the time."""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from bothsides import config
from bothsides.matching.factory import build_matcher
from bothsides.matching.gemini import GeminiMatcher
from bothsides.matching.types import MatcherError
from bothsides.server.budget import Budget
from bothsides.server.online import OnlineApp

from .fakes import FakeGeminiClient, FakeInteraction, ManualClock, gemini_json, gemini_reply
from .helpers import SISTER_RECEIVER, SISTER_SENDER, START
from .test_online import SECRET, Visitor

ROOT = Path(__file__).resolve().parents[1]
RECEIVER, SENDER = "брат прислал за аренду", "брату за аренду"
HELD = gemini_json(probability=0.0, same_relation="false", same_reason="false")


class InternalServerError(Exception):
    """Like the SDK's error for HTTP 5xx."""


def asked(client: FakeGeminiClient) -> list[str]:
    return [call["model"] for call in client.interactions.calls]


# -- the limits ---------------------------------------------------------------------------------


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(START)


def test_one_visitor_has_a_share(clock: ManualClock) -> None:
    budget = Budget(clock)
    with budget.of("a"):
        answers = [budget.may_ask() for _ in range(config.ONLINE_GEMINI_SHARE + 3)]
    assert answers == [True] * config.ONLINE_GEMINI_SHARE + [False] * 3
    with budget.of("b"):
        assert budget.may_ask()
    clock.advance(seconds=61)
    with budget.of("a"):
        assert budget.may_ask()


def test_all_visitors_together_have_a_limit_a_minute(clock: ManualClock) -> None:
    budget, granted = Budget(clock), 0
    for number in range(config.ONLINE_GEMINI_CALLS + 20):
        with budget.of(f"visitor {number}"):
            granted += budget.may_ask()
    assert granted == config.ONLINE_GEMINI_CALLS


def test_there_is_a_limit_a_day(clock: ManualClock) -> None:
    budget, granted = Budget(clock), 0
    for minute in range(60):
        for number in range(config.ONLINE_GEMINI_CALLS):
            with budget.of(f"{minute} {number}"):
                granted += budget.may_ask()
        clock.advance(seconds=61)
    assert granted == config.ONLINE_GEMINI_CALLS_A_DAY
    clock.advance(hours=25)
    with budget.of("tomorrow"):
        assert budget.may_ask()


def test_a_refused_visitor_costs_the_others_nothing(clock: ManualClock) -> None:
    budget = Budget(clock)
    with budget.of("greedy"):
        for _ in range(config.ONLINE_GEMINI_CALLS * 3):
            budget.may_ask()
    others = 0
    for number in range(config.ONLINE_GEMINI_CALLS):
        with budget.of(f"visitor {number}"):
            others += budget.may_ask()
    assert others == config.ONLINE_GEMINI_CALLS - config.ONLINE_GEMINI_SHARE


def play(visitor: Visitor) -> Any:
    visitor.post("/api/scenes/sister/start")
    visitor.answer("receiver", SISTER_RECEIVER)
    visitor.answer("sender", SISTER_SENDER)
    return visitor.get("/api/stage")["case"]


def test_a_greedy_visitor_does_not_take_the_model_from_the_stage(clock: ManualClock) -> None:
    client = FakeGeminiClient(FakeInteraction(HELD))
    budget = Budget(clock)
    setup = build_matcher(False, {"GEMINI_API_KEY": "unit-test"}, lambda key: client, budget.may_ask)
    app = OnlineApp(setup, clock, SECRET, budget)
    greedy, presenter = Visitor(app), Visitor(app)
    cases = [play(greedy) for _ in range(config.ONLINE_GEMINI_SHARE + 2)]
    assert [case["state"] for case in cases[-3:]] == ["held", "with_specialist", "with_specialist"]
    assert cases[-1]["match"]["fallback_code"] == "rate_limited"
    assert play(presenter)["state"] == "held"
    assert len(client.interactions.calls) == config.ONLINE_GEMINI_SHARE + 1


# -- the models share the time ----------------------------------------------------------------


def with_models(reply: Any, timeout: float = 20.0, **kwargs: Any) -> tuple[GeminiMatcher, FakeGeminiClient]:
    client = FakeGeminiClient(reply)
    subject = GeminiMatcher(client, "a", timeout_seconds=timeout, **kwargs)
    subject.use_model("a", ("b", "c"))
    return subject, client


def test_every_request_is_counted_not_every_comparison() -> None:
    left = iter([True, True, False])
    subject, client = with_models(InternalServerError("busy"), may_ask=lambda: next(left))
    with pytest.raises(MatcherError) as caught:
        subject.compare(RECEIVER, SENDER)
    assert (caught.value.code, asked(client)) == ("server_error", ["a", "b"])


def test_when_google_is_slow_the_second_model_gets_all_the_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "GEMINI_TRY_SECONDS", 0.15)
    monkeypatch.setattr(config, "GEMINI_NEXT_TRY_SECONDS", 0.1)

    def slow(request: dict[str, Any]) -> FakeInteraction:
        time.sleep(0.5)
        return gemini_reply()

    subject, client = with_models(slow, timeout=2.0)
    started = time.monotonic()
    assert subject.compare(RECEIVER, SENDER).model == "b"
    assert asked(client) == ["a", "b"]
    assert time.monotonic() - started < 1.5


def test_a_comparison_never_takes_longer_than_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "GEMINI_TRY_SECONDS", 0.2)
    monkeypatch.setattr(config, "GEMINI_NEXT_TRY_SECONDS", 0.1)

    def never(request: dict[str, Any]) -> FakeInteraction:
        time.sleep(3)
        return gemini_reply()

    subject, _ = with_models(never, timeout=0.8)
    started = time.monotonic()
    with pytest.raises(MatcherError) as caught:
        subject.compare(RECEIVER, SENDER)
    assert caught.value.code == "timeout"
    assert time.monotonic() - started < 1.3


def test_the_main_model_gets_its_place_back(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    busy = {"a"}
    subject, client = with_models(lambda request: InternalServerError("busy") if request["model"] in busy else gemini_reply())
    subject.compare(RECEIVER, SENDER)
    busy.clear()
    for _ in range(5):
        now[0] += config.GEMINI_KEEP_SECONDS / 4
        subject.compare(RECEIVER, SENDER)
    assert asked(client)[:2] == ["a", "b"]
    assert asked(client)[-1] == "a"


# -- measurements name the model that answered ---------------------------------------------------


@pytest.mark.parametrize("name", ["evaluate", "live_check"])
def test_a_measurement_asks_one_model_only(name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "evaluation"))
    module = importlib.import_module(name)
    client = FakeGeminiClient(
        lambda request: InternalServerError("busy") if request["model"] == "gemini-3.8-flash" else gemini_reply(),
        models=["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash"],
    )
    setup = build_matcher(False, {"GEMINI_API_KEY": "unit-test"}, lambda key: client)
    monkeypatch.setattr(module, "build_matcher", lambda **kwargs: setup)
    seen: list[str] = []

    def ask(*arguments: Any, **kwargs: Any) -> Any:
        matcher = next(item for item in arguments if isinstance(item, GeminiMatcher))
        with pytest.raises(MatcherError):
            matcher.compare(RECEIVER, SENDER)
        seen.extend(asked(client))
        return ([], 0)

    if name == "evaluate":
        monkeypatch.setattr(module, "run_matcher", ask)
        module._run_gemini([], 0.0, False)
    else:
        monkeypatch.setattr(module, "run_checks", ask)
        monkeypatch.setattr(module, "load_env_file", lambda path: None)
        module.main([])
    sys.modules.pop(name, None)
    assert seen == ["gemini-3.8-flash"]
