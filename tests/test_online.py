"""The whole app online: one board per visitor that any running copy can rebuild."""

from __future__ import annotations

import json
import threading
from typing import Any

import pytest

from bothsides.matching.factory import build_matcher
from bothsides.matching.types import MatcherError, Tri
from bothsides.server.boardcookie import COOKIE, Event, Log, cookies, fitted, read
from bothsides.server.messages import Request, Response
from bothsides.server.online import OnlineApp

from .fakes import BlockingMatcher, ManualClock, StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER, START

HOST = "both-sides.vercel.app"
SECRET = b"deployment"


class Visitor:
    """A browser: keeps cookies and talks to one of several running copies."""

    def __init__(self, app: OnlineApp, address: str = "203.0.113.7") -> None:
        self.app, self.address, self.jar = app, address, {}

    def send(self, method: str, path: str, data: Any = None, origin: str = f"https://{HOST}") -> Response:
        headers = {"host": HOST, "x-forwarded-proto": "https", "cookie": "; ".join(f"{k}={v}" for k, v in self.jar.items())}
        body = b""
        if method == "POST":
            body = json.dumps(data or {}).encode()
            headers |= {"origin": origin, "content-type": "application/json"}
        response = self.app.handle(Request(method, path, headers, body, self.address))
        for name, value in response.headers:
            if name == "Set-Cookie":
                key, _, rest = value.partition("=")
                self.jar[key] = rest.split(";", 1)[0]
        return response

    def get(self, path: str) -> Any:
        return json.loads(self.send("GET", path).body)["data"]

    def post(self, path: str, data: Any = None) -> Any:
        return json.loads(self.send("POST", path, data).body)

    def case_id(self) -> str:
        return self.get("/api/phone/receiver")["case_id"]

    def answer(self, side: str, text: str) -> Any:
        return self.post(f"/api/phone/{side}/answer", {"case_id": self.case_id(), "text": text})


def copy_of_the_app(clock: ManualClock) -> OnlineApp:
    return OnlineApp(build_matcher(True, {}), clock, SECRET)


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(START)


@pytest.fixture
def visitor(clock: ManualClock) -> Visitor:
    return Visitor(copy_of_the_app(clock))


def test_scene_one_is_credited_and_staff_pages_are_open(visitor: Visitor) -> None:
    visitor.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    visitor.answer("sender", BROTHER_SENDER)
    assert visitor.get("/api/phone/receiver")["status"] == "credited"
    assert visitor.get("/api/stage")["case"]["state"] == "credited"
    assert visitor.get("/api/session") == {"staff": True}
    assert visitor.get("/api/status")["sandbox"] is True
    assert any(case["state"] == "credited" for case in visitor.get("/api/cases")["cases"])


def test_another_running_copy_shows_the_same_board(visitor: Visitor, clock: ManualClock) -> None:
    visitor.post("/api/scenes/sister/start")
    clock.advance(seconds=5)
    visitor.answer("receiver", SISTER_RECEIVER)
    clock.advance(seconds=7)
    before = visitor.get("/api/phone/sender")
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/sender") == before
    visitor.answer("sender", SISTER_SENDER)
    visitor.app = copy_of_the_app(clock)
    file = visitor.get(f"/api/cases/{visitor.case_id()}")
    assert (file["state"], file["seconds"]) == ("with_specialist", 7.0)
    assert file["reasons"] == ["low_match", "no_shared_reason", "risky_facts"]
    visitor.post(f"/api/cases/{visitor.case_id()}/return")
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/receiver")["status"] == "returned"


def test_every_request_may_meet_another_copy(visitor: Visitor, clock: ManualClock) -> None:
    for path, data in [("/api/scenes/stranger/start", None)]:
        visitor.post(path, data)
    for _ in range(2):
        visitor.app = copy_of_the_app(clock)
        clock.advance(seconds=1)
        visitor.post("/api/phone/receiver/deny", {"case_id": visitor.case_id()})
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/receiver")["status"] == "return_offer"
    visitor.post("/api/phone/receiver/accept-return", {"case_id": visitor.case_id()})
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/sender")["status"] == "returned"


def test_two_visitors_do_not_meet(visitor: Visitor) -> None:
    other = Visitor(visitor.app, "203.0.113.8")
    visitor.post("/api/scenes/brother/start")
    other.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    assert visitor.get("/api/phone/receiver")["status"] == "waiting"
    assert other.get("/api/phone/receiver")["status"] == "question"


def test_a_slow_reply_does_not_undo_what_the_server_knows(visitor: Visitor, clock: ManualClock) -> None:
    visitor.post("/api/scenes/stranger/start")
    case_id, old = visitor.case_id(), dict(visitor.jar)
    visitor.post("/api/phone/receiver/deny", {"case_id": case_id})
    visitor.jar = old  # the second tap leaves before the first reply has arrived
    clock.advance(seconds=1)
    visitor.post("/api/phone/receiver/deny", {"case_id": case_id})
    assert visitor.get("/api/phone/receiver")["status"] == "return_offer"


def test_phones_never_get_the_other_answer(visitor: Visitor) -> None:
    visitor.post("/api/scenes/sister/start")
    visitor.answer("receiver", "друг вернул долг за ремонт крыши")
    assert "крыши" not in visitor.send("GET", "/api/phone/sender").body.decode()


@pytest.mark.parametrize("change", ["cut", "flip", "other"])
def test_a_changed_cookie_is_a_new_board(visitor: Visitor, change: str) -> None:
    visitor.post("/api/scenes/sister/start")
    value = visitor.jar[f"{COOKIE}0"]
    visitor.jar[f"{COOKIE}0"] = {"cut": value[:-4], "flip": ("A" if value[0] != "A" else "B") + value[1:], "other": "AAAA"}[change]
    assert visitor.get("/api/stage")["scene"] == "brother"


def test_a_log_of_another_deployment_is_not_read() -> None:
    log = Log("r" * 24, 1, 4107, (Event(2, "/api/reset", {}),))
    header = "; ".join(value.split(";", 1)[0] for _, value in cookies(log, b"one", True))
    assert read(header, b"one") == log
    assert read(header, b"two") is None


def test_a_long_life_still_fits(visitor: Visitor, clock: ManualClock) -> None:
    for number in range(40):
        visitor.post("/api/scenes/sister/start")
        visitor.answer("receiver", f"друг вернул долг номер {number} за ремонт крыши и забора на даче у бабушки")
        visitor.answer("sender", f"сестре на лечение {number} после операции в городской больнице")
        clock.advance(seconds=30)
    assert all(len(value) < 3800 for value in visitor.jar.values())
    before = visitor.get("/api/stage")["case"]
    visitor.app = copy_of_the_app(clock)
    after = visitor.get("/api/stage")["case"]
    assert (after["id"], after["state"]) == (before["id"], "with_specialist")
    visitor.post(f"/api/cases/{after['id']}/release")
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/receiver")["status"] == "credited"


def test_fitted_keeps_the_last_scene() -> None:
    events = tuple(Event(i, "/api/scenes/sister/start" if i % 5 == 0 else "/api/phone/receiver/answer", {"text": "я" * 250}) for i in range(90))
    short = fitted(Log("r" * 24, 0, 4107, events), SECRET, 4)
    assert 0 < len(short.events) < 90
    assert short.events[-1] == events[-1]


def test_cookies_are_for_the_server_only(visitor: Visitor) -> None:
    response = visitor.send("GET", "/api/status")
    sent = [value for name, value in response.headers if name == "Set-Cookie"]
    assert sent and all("HttpOnly" in value and "Secure" in value and "SameSite=Lax" in value for value in sent)


def test_other_sites_cannot_write(visitor: Visitor) -> None:
    assert visitor.send("POST", "/api/reset", origin="https://evil.example").status == 403


def test_one_address_has_a_limit(visitor: Visitor) -> None:
    states = {visitor.send("POST", "/api/reset").status for _ in range(130)}
    assert 429 in states


# -- with a language model ----------------------------------------------------------------------


class ModelSetup:
    """A set-up around any matcher."""

    def __init__(self, matcher: Any) -> None:
        self.matcher = matcher

    def status(self) -> Any:
        return build_matcher(True, {}).status()


def model_app(answer: Any, clock: ManualClock) -> tuple[OnlineApp, Any]:
    matcher = StubMatcher(answer)
    return OnlineApp(ModelSetup(matcher), clock, SECRET), matcher


def play_sister(visitor: Visitor) -> None:
    visitor.post("/api/scenes/sister/start")
    visitor.answer("receiver", SISTER_RECEIVER)
    visitor.answer("sender", SISTER_SENDER)


def test_the_model_is_asked_once_and_its_answer_is_kept(clock: ManualClock) -> None:
    app, first = model_app(gemini_result(0.02, Tri.FALSE, Tri.FALSE), clock)
    visitor = Visitor(app)
    play_sister(visitor)
    assert visitor.get("/api/stage")["case"]["state"] == "held"
    before = visitor.get("/api/stage")["case"]
    visitor.app, second = model_app(gemini_result(0.99), clock)
    assert visitor.get("/api/stage")["case"] == before
    assert before["match"]["source"] == "gemini" and before["match"]["note"] == "Fake model note."
    visitor.post(f"/api/cases/{visitor.case_id()}/return")
    assert visitor.get("/api/phone/receiver")["status"] == "returned"
    assert (len(first.calls), len(second.calls)) == (1, 0)


def test_a_comparison_that_failed_stays_failed(clock: ManualClock) -> None:
    visitor = Visitor(model_app(MatcherError("no_matcher"), clock)[0])
    play_sister(visitor)
    before = visitor.get("/api/stage")["case"]
    visitor.app, second = model_app(gemini_result(0.99), clock)
    assert visitor.get("/api/stage")["case"] == before
    assert before["match"] is None and second.calls == []


def test_times_are_the_same_when_the_board_is_played_again(clock: ManualClock) -> None:
    class Slow(StubMatcher):
        def compare(self, receiver_text: str, sender_text: str) -> Any:
            clock.advance(seconds=4.321)
            return super().compare(receiver_text, sender_text)

    visitor = Visitor(OnlineApp(ModelSetup(Slow(gemini_result(0.02, Tri.FALSE, Tri.FALSE))), clock, SECRET))
    play_sister(visitor)
    file = visitor.get(f"/api/cases/{visitor.case_id()}")
    visitor.app = model_app(gemini_result(0.99), clock)[0]
    assert visitor.get(f"/api/cases/{visitor.case_id()}") == file


def test_phones_are_answered_while_the_model_thinks(clock: ManualClock) -> None:
    matcher = BlockingMatcher(gemini_result(0.95))
    app = OnlineApp(ModelSetup(matcher), clock, SECRET)
    visitor, other = Visitor(app), Visitor(app, "203.0.113.8")
    visitor.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    thread = threading.Thread(target=lambda: visitor.answer("sender", BROTHER_SENDER), daemon=True)
    thread.start()
    assert matcher.started.wait(5)
    assert other.get("/api/status")["sandbox"] is True
    assert Visitor.get(visitor, "/api/stage")["case"]["state"] == "comparing"
    matcher.release.set()
    thread.join(5)
    assert visitor.get("/api/phone/receiver")["status"] == "credited"


def test_a_slow_action_keeps_its_place_in_time() -> None:
    log = Log("r" * 24, 0, 4107, (Event(5, "/api/reset", {}),))
    log = log.with_event(Event(9, "/api/scenes/sister/start", {})).with_event(Event(7, "/api/phone/sender/answer", {}, (8,)))
    assert [event.at for event in log.events] == [5, 7, 9]
    header = "; ".join(value.split(";", 1)[0] for _, value in cookies(log, b"one", True))
    assert read(header, b"one") == log


def test_a_visitor_cannot_bring_a_result_along(clock: ManualClock) -> None:
    app, matcher = model_app(gemini_result(0.02, Tri.FALSE, Tri.FALSE), clock)
    visitor = Visitor(app)
    visitor.post("/api/scenes/sister/start")
    visitor.answer("receiver", SISTER_RECEIVER)
    extra = {"case_id": visitor.case_id(), "text": SISTER_SENDER, "match": [1, 0.99, "true", "true", "", "gemini", "x", ""]}
    visitor.post("/api/phone/sender/answer", extra)
    visitor.app = model_app(gemini_result(0.99), clock)[0]
    assert visitor.get("/api/stage")["case"]["state"] in {"held", "question", "awaiting_sender"}
