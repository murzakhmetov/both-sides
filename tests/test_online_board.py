"""Boards online: several running copies, late replies, long lives, many visitors behind one address."""

from __future__ import annotations

import json
import random
from typing import Any

import pytest

from bothsides import config
from bothsides.matching.types import MatchResult, MatchSource, Tri
from bothsides.server import boardcookie
from bothsides.server.boardcookie import COOKIE, SEED, Event, Log, cookies, fitted, read
from bothsides.server.messages import Request, Response
from bothsides.server.online import OnlineApp

from .fakes import ManualClock, StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER, START
from .test_online import HOST, SECRET, ModelSetup, Visitor, copy_of_the_app


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(START)


@pytest.fixture
def visitor(clock: ManualClock) -> Visitor:
    return Visitor(copy_of_the_app(clock))


def set_cookies(response: Response) -> list[str]:
    return [value for name, value in response.headers if name == "Set-Cookie"]


def take(jar: dict[str, str], response: Response) -> None:
    """What a browser does with the cookies of a reply."""
    for value in set_cookies(response):
        key, _, rest = value.partition("=")
        jar[key] = rest.split(";", 1)[0]


def model_app(answer: Any, clock: ManualClock) -> OnlineApp:
    return OnlineApp(ModelSetup(StubMatcher(answer)), clock, SECRET)


# -- first visit --------------------------------------------------------------------------------


def test_a_late_first_reply_does_not_wipe_out_the_first_action(visitor: Visitor) -> None:
    late = Visitor(visitor.app)
    reply = late.send("GET", "/api/phone/receiver")
    visitor.post("/api/scenes/sister/start")
    for value in set_cookies(reply):
        key, _, rest = value.partition("=")
        visitor.jar[key] = rest.split(";", 1)[0]
    assert visitor.get("/api/stage")["scene"] == "sister"


def test_frames_of_one_page_meet_on_one_board(visitor: Visitor, clock: ManualClock) -> None:
    frames = [Visitor(visitor.app).send("GET", path) for path in ("/api/phone/receiver", "/api/phone/sender", "/api/stage")]
    for reply in frames:
        key, _, rest = set_cookies(reply)[0].partition("=")
        assert (key, len(set_cookies(reply))) == (SEED, 1)
        visitor.jar[key] = rest.split(";", 1)[0]
    clock.advance(seconds=30)
    visitor.app = copy_of_the_app(clock)
    before = visitor.get("/api/stage")
    visitor.answer("receiver", BROTHER_RECEIVER)
    after = visitor.get("/api/stage")
    assert (after["case"]["id"], after["case"]["stopped_at"]) == (before["case"]["id"], before["case"]["stopped_at"])
    assert after["case"]["state"] == "awaiting_sender"


def test_a_visitor_who_only_looks_takes_no_room_in_the_memory(visitor: Visitor) -> None:
    for _ in range(20):
        visitor.jar = {}
        visitor.send("GET", "/api/stage")
    assert len(visitor.app._rooms) == 0


@pytest.mark.parametrize(("method", "path", "origin"), [
    ("POST", "/api/reset", "https://evil.example"), ("POST", "/api/reset", "null"), ("GET", "/api/nothing", ""), ("POST", "/api/nothing", f"https://{HOST}"),
])
def test_a_refused_request_sets_no_cookie(visitor: Visitor, method: str, path: str, origin: str) -> None:
    assert set_cookies(visitor.send(method, path, origin=origin)) == []


def test_another_site_cannot_wipe_a_board(visitor: Visitor) -> None:
    visitor.post("/api/scenes/sister/start")
    kept = dict(visitor.jar)
    visitor.jar = {}  # a form on another site brings no cookie
    for value in set_cookies(visitor.send("POST", "/api/reset", origin="https://evil.example")) + set_cookies(visitor.send("GET", "/api/status")):
        key, _, rest = value.partition("=")
        kept[key] = rest.split(";", 1)[0]
    visitor.jar = kept
    assert visitor.get("/api/stage")["scene"] == "sister"


# -- many visitors ------------------------------------------------------------------------------


def test_one_wifi_carries_many_visitors(clock: ManualClock) -> None:
    app = copy_of_the_app(clock)
    hall = [Visitor(app) for _ in range(12)]
    for person in hall:
        person.get("/api/status")
    states = {person.send("GET", "/api/phone/receiver").status for _ in range(config.RATE_LIMIT_READS // 8) for person in hall}
    assert states == {200}


def test_one_visitor_still_has_a_limit(visitor: Visitor) -> None:
    visitor.get("/api/status")
    assert 429 in {visitor.send("GET", "/api/session").status for _ in range(config.RATE_LIMIT_READS + 5)}


def test_other_sites_do_not_use_up_the_requests_of_a_visitor(visitor: Visitor) -> None:
    visitor.post("/api/scenes/sister/start")
    stranger = Visitor(visitor.app, visitor.address)
    for _ in range(config.RATE_LIMIT_WRITES + 5):
        stranger.send("POST", "/api/reset", origin="https://evil.example")
    assert visitor.send("POST", "/api/scenes/brother/start").status == 200


# -- two copies, late replies -------------------------------------------------------------------


def test_two_copies_that_saw_different_actions_agree_again(visitor: Visitor, clock: ManualClock) -> None:
    first, second = visitor.app, copy_of_the_app(clock)
    visitor.post("/api/scenes/stranger/start")
    case, jar = visitor.case_id(), dict(visitor.jar)
    clock.advance(seconds=1)
    visitor.post("/api/phone/receiver/deny", {"case_id": case})
    visitor.app, visitor.jar = second, dict(jar)
    clock.advance(seconds=1)
    visitor.post("/api/phone/receiver/deny", {"case_id": case})
    visitor.app = first
    assert visitor.get("/api/phone/receiver")["status"] == "return_offer"
    visitor.post("/api/phone/receiver/accept-return", {"case_id": case})
    visitor.app = second
    assert visitor.get("/api/phone/receiver")["status"] == "returned"


def test_a_slow_comparison_does_not_undo_what_came_from_another_copy(clock: ManualClock) -> None:
    class Interrupted(StubMatcher):
        during: Any = None

        def compare(self, receiver_text: str, sender_text: str) -> Any:
            if self.during:
                self.during()
            return super().compare(receiver_text, sender_text)

    matcher = Interrupted(gemini_result(0.95))
    visitor = Visitor(OnlineApp(ModelSetup(matcher), clock, SECRET))
    visitor.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    case, other = visitor.case_id(), Visitor(copy_of_the_app(clock))

    def meanwhile() -> None:
        other.jar = dict(visitor.jar)
        clock.advance(seconds=1)
        other.post("/api/scenes/sister/start")
        third = Visitor(visitor.app)
        third.jar = dict(other.jar)
        assert third.get("/api/stage")["scene"] == "sister"
        clock.advance(seconds=2)

    matcher.during = meanwhile
    visitor.post("/api/phone/sender/answer", {"case_id": case, "text": BROTHER_SENDER})
    matcher.during = None
    for app in (visitor.app, other.app, model_app(gemini_result(0.0), clock)):
        visitor.app = app
        assert visitor.get("/api/stage")["scene"] == "sister"
        assert visitor.get(f"/api/cases/{case}")["state"] == "credited"


def test_two_replies_in_any_order_lose_nothing(clock: ManualClock) -> None:
    class Interrupted(StubMatcher):
        during: Any = None

        def compare(self, receiver_text: str, sender_text: str) -> Any:
            if self.during:
                self.during()
            return super().compare(receiver_text, sender_text)

    for action in ("/api/scenes/stranger/start", "/api/scenes/brother/start", "/api/reset"):
        matcher = Interrupted(gemini_result(0.02, Tri.FALSE, Tri.FALSE))
        visitor = Visitor(OnlineApp(ModelSetup(matcher), clock, SECRET))
        visitor.post("/api/scenes/sister/start")
        visitor.answer("receiver", SISTER_RECEIVER)
        case, other = visitor.case_id(), Visitor(copy_of_the_app(clock))

        def meanwhile() -> None:
            clock.advance(seconds=1)
            other.jar = dict(visitor.jar)
            take(visitor.jar, other.send("POST", action))
            clock.advance(seconds=2)

        matcher.during = meanwhile
        visitor.post("/api/phone/sender/answer", {"case_id": case, "text": SISTER_SENDER})
        matcher.during = None
        boards = []
        for app in (visitor.app, other.app, model_app(gemini_result(0.99), clock)):
            visitor.app = app
            boards.append(seen(visitor))
        assert boards[0] == boards[1] == boards[2], action
        assert boards[0]["stage"]["scene"] == ("stranger" if "stranger" in action else "brother")


def test_two_taps_on_two_copies_before_the_first_reply(visitor: Visitor, clock: ManualClock) -> None:
    visitor.post("/api/scenes/stranger/start")
    case, copies = visitor.case_id(), [visitor.app, copy_of_the_app(clock)]
    phones, replies = [Visitor(app) for app in copies], []
    for phone in phones:
        phone.jar = dict(visitor.jar)
        clock.advance(milliseconds=301)
        replies.append(phone.send("POST", "/api/phone/receiver/deny", {"case_id": case}))
    for reply in replies:
        take(visitor.jar, reply)
    for app in (*copies, copy_of_the_app(clock)):
        visitor.app = app
        assert visitor.get("/api/phone/receiver")["status"] == "return_offer"


def test_what_happened_during_a_comparison_counts_when_it_is_played_again(clock: ManualClock) -> None:
    class Interrupted(StubMatcher):
        during: Any = None

        def compare(self, receiver_text: str, sender_text: str) -> Any:
            happened, self.during = self.during, None
            if happened:
                happened()
            return super().compare(receiver_text, sender_text)

    told = "брату моя половина аренды квартиры"
    matcher = Interrupted(gemini_result(0.95))
    visitor = Visitor(OnlineApp(ModelSetup(matcher), clock, SECRET))
    visitor.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    case, second = visitor.case_id(), Visitor(visitor.app)

    def meanwhile() -> None:
        second.jar = dict(visitor.jar)
        for scene in ("sister", "stranger"):
            clock.advance(seconds=1)
            second.post(f"/api/scenes/{scene}/start")
            second.answer("receiver", "брат прислал за аренду")
            clock.advance(seconds=1)
            second.answer("sender", told)

    matcher.during = meanwhile
    visitor.post("/api/phone/sender/answer", {"case_id": case, "text": told})
    before = visitor.get(f"/api/cases/{case}")
    visitor.app = model_app(gemini_result(0.0), clock)
    after = visitor.get(f"/api/cases/{case}")
    assert "repeated_story" in before["reasons"]
    assert after == before


# -- long lives ---------------------------------------------------------------------------------

_WORDS = "аренда квартира ремонт лечение долг подарок билет мебель школа учёба свадьба дом дача окно дверь кран".split()


def story(dice: random.Random, start: str) -> str:
    return f"{start} {' '.join(dice.choice(_WORDS) for _ in range(6))} {dice.choice(_WORDS)}"


def note(dice: random.Random) -> MatchResult:
    text = " ".join(dice.choice(["Both", "answers", "name", "rent", "treatment", "brother", "sister", "differ", "agree", "reason"]) for _ in range(28))
    return MatchResult(round(dice.random(), 2), Tri.TRUE, dice.choice(list(Tri)), text[: config.MAX_NOTE_LENGTH], MatchSource.GEMINI, "gemini-3.5-flash")


class Dice:
    """Random actions of one visitor, the same on every board that gets them."""

    def __init__(self, seed: int) -> None:
        self.dice = random.Random(seed)

    def action(self, visitor: Visitor) -> tuple[str, dict[str, str]]:
        phone = visitor.get("/api/stage")
        case, state = phone["case"]["id"], phone["case"]["state"]
        roll = self.dice.random()
        if roll < 0.22:
            return f"/api/scenes/{self.dice.choice(['brother', 'sister', 'stranger'])}/start", {}
        if roll < 0.24:
            return "/api/reset", {}
        if roll < 0.34:
            known = [item["id"] for item in visitor.get("/api/cases")["cases"]]
            return f"/api/cases/{self.dice.choice(known)}/{self.dice.choice(['release', 'return'])}", {}
        if state == "awaiting_receiver":
            if roll < 0.5:
                return "/api/phone/receiver/deny", {"case_id": case}
            return "/api/phone/receiver/answer", {"case_id": case, "text": story(self.dice, "брат прислал")}
        if state == "awaiting_sender":
            return "/api/phone/sender/answer", {"case_id": case, "text": story(self.dice, "брату за")}
        if state == "return_offer":
            return "/api/phone/receiver/accept-return", {"case_id": case}
        return f"/api/phone/{self.dice.choice(['receiver', 'sender'])}/objection", {"case_id": case}


def seen(visitor: Visitor) -> dict[str, Any]:
    board = visitor.get("/api/cases")
    files = [visitor.get(f"/api/cases/{item['id']}") for item in board["cases"]]
    return {"board": board, "files": files, "stage": visitor.get("/api/stage"), "phones": [visitor.get(f"/api/phone/{side}") for side in ("receiver", "sender")]}


def live_a_life(seed: int, actions: int, clock: ManualClock, answers: Any) -> None:
    """The same actions on one copy that never forgets and on three copies that answer in turn."""
    dice = Dice(seed)
    calls = random.Random(seed + 1)
    one = Visitor(OnlineApp(ModelSetup(answers(seed)), clock, SECRET))
    copies = [OnlineApp(ModelSetup(answers(seed)), clock, SECRET) for _ in range(3)]
    many = Visitor(copies[0])
    results = answers(seed)
    for app in (one.app, *copies):
        app._setup = ModelSetup(results)
    for visitor in (one, many):
        visitor.get("/api/status")
    many.jar = dict(one.jar)
    for number in range(actions):
        clock.advance(milliseconds=calls.randint(40, 20_000))
        path, data = dice.action(one)
        results.turn = number
        old = dict(many.jar)
        many.app = calls.choice(copies)
        first, second = one.send("POST", path, data), many.send("POST", path, data)
        assert first.status == second.status, (number, path, first.body[:200], second.body[:200])
        late = Visitor(calls.choice(copies))
        late.jar = old
        late.get("/api/stage")
        many.app = calls.choice(copies)
        assert seen(many) == seen(one), (number, path)


class Scripted:
    """One answer per action, the same for every board that asks."""

    def __init__(self, seed: int) -> None:
        self.seed, self.turn = seed, 0

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        return note(random.Random(self.seed * 10_000 + self.turn))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_three_copies_show_what_one_copy_shows(seed: int, clock: ManualClock) -> None:
    live_a_life(seed, 60, clock, Scripted)


@pytest.mark.parametrize("seed", [4, 5, 6])
def test_shortened_logs_show_the_same_board(seed: int, clock: ManualClock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boardcookie, "_PARTS", 1)
    monkeypatch.setattr(boardcookie, "_PART_LENGTH", 1900)
    live_a_life(seed, 90, clock, Scripted)


def test_an_old_cookie_does_not_bring_back_what_a_shortened_log_has_dropped(visitor: Visitor, clock: ManualClock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boardcookie, "_PARTS", 1)
    monkeypatch.setattr(boardcookie, "_PART_LENGTH", 900)
    dice, jars = random.Random(7), []
    other = copy_of_the_app(clock)
    for _ in range(12):
        visitor.post("/api/scenes/sister/start")
        visitor.answer("receiver", story(dice, "друг вернул"))
        visitor.answer("sender", story(dice, "сестре на"))
        jars.append(dict(visitor.jar))
        clock.advance(seconds=20)
    visitor.post("/api/scenes/stranger/start")
    new = dict(visitor.jar)
    for old in jars:
        for app in (visitor.app, other):
            late = Visitor(app)
            late.jar = old
            late.get("/api/stage")
            visitor.app, visitor.jar = app, dict(new)
            assert visitor.get("/api/stage")["scene"] == "stranger"


def test_a_repeated_story_stays_repeated_in_a_shortened_log(clock: ManualClock, monkeypatch: pytest.MonkeyPatch) -> None:
    visitor = Visitor(copy_of_the_app(clock))
    dice, told = random.Random(8), "брату моя половина аренды квартиры"
    for scene in ("sister", "stranger"):
        visitor.post(f"/api/scenes/{scene}/start")
        visitor.answer("receiver", "брат прислал за аренду")
        visitor.answer("sender", told)
    visitor.post("/api/scenes/brother/start")
    visitor.answer("receiver", BROTHER_RECEIVER)
    visitor.answer("sender", told)
    before = visitor.get("/api/stage")["case"]
    assert "repeated_story" in before["reasons"]
    for scene in ("sister", "stranger") * 8:
        clock.advance(seconds=9)
        visitor.post(f"/api/scenes/{scene}/start")
        visitor.answer("receiver", story(dice, "друг вернул"))
        visitor.answer("sender", story(dice, "сестре на"))
    log = read("; ".join(f"{key}={value}" for key, value in visitor.jar.items()), SECRET)
    assert log is not None
    short = log.without_forgotten(4)
    assert len(short.events) < len(log.events) - 20
    monkeypatch.setattr(boardcookie, "_MAX_EVENTS", len(short.events))
    visitor.jar = {key: value.split(";", 1)[0].partition("=")[2] for key, value in zip((f"{COOKIE}{i}" for i in range(3)), (v for _, v in cookies(short, SECRET, True)))}
    visitor.app = copy_of_the_app(clock)
    after = visitor.get(f"/api/cases/{before['id']}")
    assert (after["state"], after["reasons"]) == (before["state"], before["reasons"])


def test_real_lives_fit_for_a_long_time(clock: ManualClock) -> None:
    dice = random.Random(9)
    visitor = Visitor(model_app(None, clock))
    for number in range(60):
        visitor.app._setup.matcher.result = note(dice)
        visitor.post(f"/api/scenes/{('brother', 'sister', 'stranger')[number % 3]}/start")
        visitor.answer("receiver", story(dice, "брат прислал"))
        visitor.answer("sender", story(dice, "брату за"))
        clock.advance(seconds=25)
    assert sum(len(value) for value in visitor.jar.values()) < 14_500
    before = seen(visitor)
    visitor.app = model_app(gemini_result(0.5), clock)
    assert seen(visitor) == before
    assert before["stage"]["case"]["id"].endswith(f"-{4111 + 60}")


def test_the_last_resort_still_ends(clock: ManualClock) -> None:
    dice = random.Random(10)
    letters = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
    events = tuple(
        Event(i + 1, "/api/phone/receiver/answer", {"case_id": "BS-2026-4111", "text": "".join(dice.choice(letters) for _ in range(300))}) for i in range(200)
    )
    assert len(cookies(fitted(Log("r" * 24, 0, 4107, events), SECRET, 4), SECRET, True)) == 3


def test_a_log_that_packs_well_can_still_be_read(clock: ManualClock) -> None:
    events = tuple(Event(i + 1, "/api/phone/receiver/answer", {"case_id": "BS-2026-4111", "text": "я" * 300}) for i in range(200))
    log = fitted(Log("r" * 24, 0, 4107, events), SECRET, 4)
    header = "; ".join(value.split(";", 1)[0] for _, value in cookies(log, SECRET, True))
    assert read(header, SECRET) == log


# -- strange bodies -----------------------------------------------------------------------------


def raw_post(visitor: Visitor, path: str, body: bytes) -> Response:
    headers = {
        "host": HOST, "origin": f"https://{HOST}", "content-type": "application/json", "x-forwarded-proto": "https",
        "cookie": "; ".join(f"{key}={value}" for key, value in visitor.jar.items()),
    }
    response = visitor.app.handle(Request("POST", path, headers, body, visitor.address))
    for value in set_cookies(response):
        key, _, rest = value.partition("=")
        visitor.jar[key] = rest.split(";", 1)[0]
    return response


def test_half_a_character_is_kept_like_any_other(visitor: Visitor, clock: ManualClock) -> None:
    visitor.post("/api/scenes/sister/start")
    body = b'{"case_id": "' + visitor.case_id().encode() + b'", "text": "\\u0434\\u0440\\u0443\\u0433 \\ud83d \\u0434\\u043e\\u043b\\u0433"}'
    assert raw_post(visitor, "/api/phone/receiver/answer", body).status == 200
    visitor.app = copy_of_the_app(clock)
    assert visitor.get("/api/phone/receiver")["status"] == "waiting"


@pytest.mark.parametrize("body", [
    json.dumps({"x": random.Random(1).randbytes(3000).hex()}).encode(),
    json.dumps({"text": random.Random(2).randbytes(2000).hex(), "case_id": random.Random(3).randbytes(900).hex()}).encode(),
    b'{"x": ' + b"[" * 900 + b"]" * 900 + b"}",
])
def test_a_body_that_nobody_reads_is_not_kept(visitor: Visitor, clock: ManualClock, body: bytes) -> None:
    for _ in range(3):
        raw_post(visitor, "/api/scenes/sister/start", body)
        clock.advance(seconds=1)
    extra = {"case_id": visitor.case_id(), "text": SISTER_RECEIVER, "more": random.Random(4).randbytes(1500).hex()}
    assert raw_post(visitor, "/api/phone/receiver/answer", json.dumps(extra).encode()).status == 200
    assert sum(len(value) for value in visitor.jar.values()) < 1500
    before = seen(visitor)
    visitor.app = copy_of_the_app(clock)
    assert seen(visitor) == before


def test_the_scene_of_the_page_stays(visitor: Visitor, clock: ManualClock) -> None:
    visitor.post("/api/scenes/sister/start")
    visitor.answer("receiver", SISTER_RECEIVER)
    visitor.answer("sender", SISTER_SENDER)
    board = seen(visitor)
    visitor.app = copy_of_the_app(clock)
    assert seen(visitor) == board
