"""The whole app for a host that keeps nothing between requests (functions on Vercel).

Every visitor has a board of their own. What happened on it travels in signed cookies, so any
running copy of the function can play it again; the memory here only saves that work. A board
that is played again asks no matcher: every comparison stands in the log. Staff pages are open:
a visitor sees nothing but their own board with invented people.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from collections import OrderedDict
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .. import config
from ..cases.service import CaseService
from ..clock import Clock
from ..config import BANK_TIMEZONE
from ..demo.seed import background_cases
from ..matching.factory import MatcherSetup
from ..matching.types import Matcher, MatcherError, MatchResult, MatchSource, Tri
from .app import App
from .auth import StaffAuth, random_password
from .budget import Budget
from .boardcookie import Event, Log, cookies, fitted, read, seed_cookie
from .messages import Request, Response, error_response
from .ratelimit import RateLimiter
from .security import SECURITY_HEADERS

_LOG = logging.getLogger(__name__)
_MAX_ROOMS = 300
#: The same on every new board, so that the frames of one page never show different numbers.
_FIRST_NUMBER = 4107
#: What the routes of a phone read from a request.
_FIELDS = ("case_id", "text")
#: These change nothing on a board.
_NOT_KEPT = frozenset({"/api/try", "/api/login", "/api/logout"})
_REPLAY_HEADERS = {"host": "replay.invalid", "origin": "https://replay.invalid", "content-type": "application/json"}


class _EveryHost(frozenset):  # type: ignore[type-arg]
    """The platform lets only the addresses of this project through."""

    def __contains__(self, item: object) -> bool:
        return True


def _milliseconds(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _moment(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).astimezone(BANK_TIMEZONE)


def _kept(result: MatchResult) -> tuple[Any, ...]:
    """The result as plain values for the log."""
    return (
        result.probability, result.same_relation.value, result.same_reason.value, result.note,
        result.source.value, result.model, result.fallback_code,
    )


def _result(kept: tuple[Any, ...]) -> MatchResult:
    probability, relation, reason, note, source, model, code = kept
    return MatchResult(probability, Tri(relation), Tri(reason), note, MatchSource(source), model, code)


@dataclass(slots=True)
class _Turn:
    """One action on a board: made now, or played again from the log.

    *match* is the comparison it led to: when it ended, then the result, if there was one.
    """

    at: int
    again: bool = False
    match: tuple[Any, ...] | None = None
    ended: int = 0

    @property
    def moment(self) -> datetime:
        return _moment(max(self.at, self.ended))


class _Turns(threading.local):
    """The turn that this thread makes. A phone that only reads makes none."""

    now: _Turn | None = None


class _BoardClock:
    """The real clock. In a turn its moment, so that playing it again gives the same times."""

    def __init__(self, real: Clock, turns: _Turns) -> None:
        self._real = real
        self._turns = turns

    def now(self) -> datetime:
        turn = self._turns.now
        return turn.moment if turn else self._real.now()


class _BoardMatcher:
    """Asks once. A turn that is played again gets what its log kept."""

    def __init__(self, real: Matcher, clock: Clock, turns: _Turns) -> None:
        self._real = real
        self._clock = clock
        self._turns = turns

    def compare(self, receiver_text: str, sender_text: str) -> MatchResult:
        turn = self._turns.now
        if turn is None:
            raise MatcherError("no_matcher")
        if turn.again:
            return self._played(turn)
        kept: tuple[Any, ...] = ()
        try:
            result = self._real.compare(receiver_text, sender_text)
            kept = _kept(result)
            return result
        finally:
            turn.ended = _milliseconds(self._clock.now())
            turn.match = (turn.ended, *kept)

    @staticmethod
    def _played(turn: _Turn) -> MatchResult:
        if turn.match is None or len(turn.match) < 2:
            turn.ended = turn.match[0] if turn.match else 0
            raise MatcherError("no_matcher")
        turn.ended = turn.match[0]
        return _result(turn.match[1:])


class _Comparisons:
    """Compares before the reply: after it, the host may stop the function.

    A comparison that is played again waits for the moment when it ended, because what
    happened meanwhile may have changed the decision.
    """

    def __init__(self, turns: _Turns) -> None:
        self._turns = turns
        self._waiting: list[tuple[_Turn, Callable[[], None]]] = []

    def submit(self, work: Callable[[], None]) -> None:
        turn = self._turns.now
        if turn is None or not turn.again or not turn.match:
            work()
        else:
            self._waiting = sorted((*self._waiting, (turn, work)), key=lambda item: item[0].match[0])

    def end(self, before: float) -> None:
        """Play the ends of the comparisons that had ended *before* this time."""
        while self._waiting and self._waiting[0][0].match[0] < before:
            (turn, work), *self._waiting = self._waiting
            self._turns.now = turn
            work()
            self._turns.now = None


class SandboxApp(App):
    """One visitor's app. The visitor plays the clients and the staff."""

    sandbox = True

    def is_staff(self, request: Request) -> bool:
        return True


@dataclass(slots=True)
class _Room:
    app: SandboxApp
    turns: _Turns
    log: Log

    def handle(self, request: Request, turn: _Turn | None) -> Response:
        """Let the app answer; *turn* is what its clock and its matcher see."""
        self.turns.now = turn
        try:
            return self.app.handle(request)
        finally:
            self.turns.now = None


def _fields(request: Request) -> dict[str, str]:
    """What an action on a phone says. Read before the action: a strange body must not fail after it."""
    if request.method != "POST" or not request.path.startswith("/api/phone/"):
        return {}
    try:
        data = json.loads(request.body)
    except (ValueError, RecursionError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {name: data[name] for name in _FIELDS if isinstance(data.get(name), str)}


class OnlineApp:
    """Finds or rebuilds the visitor's board and lets its app answer."""

    def __init__(self, setup: MatcherSetup, clock: Clock, secret: bytes, budget: Budget | None = None) -> None:
        self._budget = budget
        self._setup = setup
        self._clock = clock
        self._secret = secret
        self._rooms: OrderedDict[str, _Room] = OrderedDict()
        self._lock = threading.RLock()
        self._reads = RateLimiter(config.RATE_LIMIT_READS, config.RATE_WINDOW)
        self._writes = RateLimiter(config.RATE_LIMIT_WRITES, config.RATE_WINDOW)
        self._reads_here = RateLimiter(config.ONLINE_READS_PER_ADDRESS, config.RATE_WINDOW)
        self._writes_here = RateLimiter(config.ONLINE_WRITES_PER_ADDRESS, config.RATE_WINDOW)
        # Never used to sign in: the pages are open. Only the routes need an object.
        self._auth = StaffAuth(random_password(), clock, iterations=1)
        self._background = background_cases(clock.now(), 0)[2]

    def handle(self, request: Request) -> Response:
        """Answer one request. Never raises."""
        try:
            return self._answer(request)
        except Exception as error:
            # The message may hold user text, so only the class name is logged.
            _LOG.error("request failed: %s", type(error).__name__)
            return error_response(500, "server_error").with_headers(*SECURITY_HEADERS)

    def _answer(self, request: Request) -> Response:
        sent = read(request.headers.get("cookie", ""), self._secret)
        # Visitors behind one address (one Wi-Fi) do not use up each other's requests.
        visitor = sent.room if sent else request.address
        wait = self._wait(request, visitor)
        if wait > 0:
            return error_response(429, "rate_limited", (("Retry-After", str(wait)),)).with_headers(*SECURITY_HEADERS)
        with self._lock:
            room = self._room(sent)
            turn = self._turn(room.log) if request.method == "POST" else None
        fields = _fields(request)
        # Without the lock: the language model takes seconds, and the other phones go on asking.
        with self._budget.of(visitor, request.address) if self._budget else nullcontext():
            response = room.handle(request, turn)
        secure = request.headers.get("x-forwarded-proto", "") == "https"
        if turn is not None and response.status == 200 and request.path not in _NOT_KEPT:
            event = Event(turn.at, request.path, fields, turn.match)
            log = self._kept(room, event)
            return Response(response.status, (*response.headers, *cookies(log, self._secret, secure, event)), response.body)
        if turn is None and response.status == 200:
            return Response(response.status, (*response.headers, *self._news(sent, room, secure)), response.body)
        return response

    def _wait(self, request: Request, visitor: str) -> int:
        """Seconds to wait, for one visitor and for one address with all its visitors."""
        post, now = request.method == "POST", self._clock.now()
        own, shared = (self._writes, self._writes_here) if post else (self._reads, self._reads_here)
        return own.wait_seconds(visitor, now) or shared.wait_seconds(request.address, now)

    def _news(self, sent: Log | None, room: _Room, secure: bool) -> tuple[tuple[str, str], ...]:
        """The cookies that a visitor who only looks needs.

        A visitor who has done nothing yet gets a board. Its cookie has a name of its own: a late
        reply must not wipe out the first action. And when the reply to an action got lost (the
        page was left while the model was thinking), the board knows more than the cookies.
        """
        if sent is None:
            return (seed_cookie(room.log, self._secret, secure),)
        with self._lock:
            log = room.log
        if log == sent:
            return ()
        return cookies(fitted(log, self._secret, self._background), self._secret, secure)

    def _kept(self, room: _Room, event: Event) -> Log:
        """Put what happened into the log of the board."""
        with self._lock:
            current = self._rooms.get(room.log.room, room)
            log = fitted(current.log.merged(room.log).with_event(event), self._secret, self._background)
            if current is room:
                room.log = log
            else:
                # News from another running copy came in while the model was thinking.
                current = self._rebuilt(log)
            self._remember(current)
            return log

    def _turn(self, log: Log) -> _Turn:
        """A turn that begins now, and after everything that this board already knows."""
        return _Turn(max(_milliseconds(self._clock.now()), log.last + 1))

    def _room(self, sent: Log | None) -> _Room:
        if sent is None:
            return self._rebuilt(Log(secrets.token_urlsafe(18), _milliseconds(self._clock.now()), _FIRST_NUMBER))
        known = self._rooms.get(sent.room)
        # The memory may know more than a cookie that a slow reply has not brought yet, and less
        # than one that another running copy has written.
        log = known.log.merged(sent) if known else sent
        if known is None or log != known.log:
            known = self._rebuilt(log)
        self._remember(known)
        return known

    def _remember(self, room: _Room) -> None:
        self._rooms[room.log.room] = room
        self._rooms.move_to_end(room.log.room)
        while len(self._rooms) > _MAX_ROOMS:
            self._rooms.popitem(last=False)

    def _rebuilt(self, log: Log) -> _Room:
        turns = _Turns()
        clock = _BoardClock(self._clock, turns)
        turns.now = _Turn(log.created, again=True)
        matcher = _BoardMatcher(self._setup.matcher, self._clock, turns)
        comparisons = _Comparisons(turns)
        service = CaseService(clock=clock, matcher=matcher, executor=comparisons, first_number=log.first)
        room = _Room(SandboxApp(service, self._auth, self._setup, clock, allowed_hosts=_EveryHost()), turns, log)
        for event in log.events:
            comparisons.end(event.at)
            body = json.dumps(event.data).encode("utf-8")
            again = _Turn(event.at, again=True, match=event.match)
            room.handle(Request("POST", event.path, _REPLAY_HEADERS, body, "replay"), again)
        comparisons.end(float("inf"))
        turns.now = None
        return room
