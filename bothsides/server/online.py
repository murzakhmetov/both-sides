"""The whole app for a host that keeps nothing between requests (functions on Vercel).

Every visitor has a board of their own. What happened on it travels in signed cookies, so any
running copy of the function can play it again; the memory here only saves that work. Staff
pages are open: a visitor sees nothing but their own board with invented people.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .. import config
from ..cases.service import CaseService
from ..clock import Clock
from ..config import BANK_TIMEZONE
from ..demo.seed import background_cases
from ..matching.factory import MatcherSetup
from .app import App
from .auth import StaffAuth, random_password
from .boardcookie import Event, Log, cookies, fitted, read
from .messages import Request, Response, error_response
from .ratelimit import RateLimiter
from .security import SECURITY_HEADERS

_LOG = logging.getLogger(__name__)
_MAX_ROOMS = 300
#: The same on every new board, so that the frames of one page never show different numbers.
_FIRST_NUMBER = 4107
#: These change nothing on a board.
_NOT_KEPT = frozenset({"/api/try", "/api/login", "/api/logout"})
_REPLAY_HEADERS = {"host": "replay.invalid", "origin": "https://replay.invalid", "content-type": "application/json"}


class _EveryHost(frozenset):  # type: ignore[type-arg]
    """The platform lets only the addresses of this project through."""

    def __contains__(self, item: object) -> bool:
        return True


class _RoomClock:
    """The real clock, or a moment of the past while a board is played again."""

    def __init__(self, real: Clock) -> None:
        self._real = real
        self.moment: datetime | None = None

    def now(self) -> datetime:
        return self.moment or self._real.now()


class _AtOnce:
    """Compares before the reply: after it, the host may stop the function."""

    def submit(self, work: Callable[[], None]) -> None:
        work()


class SandboxApp(App):
    """One visitor's app. The visitor plays the clients and the staff."""

    sandbox = True

    def is_staff(self, request: Request) -> bool:
        return True


@dataclass(slots=True)
class _Room:
    app: SandboxApp
    clock: _RoomClock
    log: Log


def _milliseconds(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _moment(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).astimezone(BANK_TIMEZONE)


class OnlineApp:
    """Finds or rebuilds the visitor's board and lets its app answer."""

    def __init__(self, setup: MatcherSetup, clock: Clock, secret: bytes) -> None:
        self._setup = setup
        self._clock = clock
        self._secret = secret
        self._rooms: OrderedDict[str, _Room] = OrderedDict()
        self._lock = threading.RLock()
        self._reads = RateLimiter(config.RATE_LIMIT_READS, config.RATE_WINDOW)
        self._writes = RateLimiter(config.RATE_LIMIT_WRITES, config.RATE_WINDOW)
        # Never used to sign in: the pages are open. Only the routes need an object.
        self._auth = StaffAuth(random_password(), clock, iterations=1)
        self._background = background_cases(clock.now(), 0)[2]

    def handle(self, request: Request) -> Response:
        """Answer one request. Never raises."""
        try:
            with self._lock:
                return self._answer(request)
        except Exception as error:
            # The message may hold user text, so only the class name is logged.
            _LOG.error("request failed: %s", type(error).__name__)
            return error_response(500, "server_error").with_headers(*SECURITY_HEADERS)

    def _answer(self, request: Request) -> Response:
        limiter = self._writes if request.method == "POST" else self._reads
        wait = limiter.wait_seconds(request.address, self._clock.now())
        if wait > 0:
            return error_response(429, "rate_limited", (("Retry-After", str(wait)),)).with_headers(*SECURITY_HEADERS)
        sent = read(request.headers.get("cookie", ""), self._secret)
        room = self._room(sent)
        response = room.app.handle(request)
        kept = request.method == "POST" and response.status == 200 and request.path not in _NOT_KEPT
        if kept:
            event = Event(_milliseconds(self._clock.now()), request.path, json.loads(request.body or b"{}"))
            room.log = fitted(room.log.with_event(event), self._secret, self._background)
        if kept or sent is None:
            secure = request.headers.get("x-forwarded-proto", "") == "https"
            return Response(response.status, (*response.headers, *cookies(room.log, self._secret, secure)), response.body)
        return response

    def _room(self, sent: Log | None) -> _Room:
        log = sent or Log(secrets.token_urlsafe(18), _milliseconds(self._clock.now()), _FIRST_NUMBER)
        known = self._rooms.get(log.room)
        # The memory may be ahead of a cookie that a slow reply has not brought yet.
        if known is None or (len(log.events), log.created) > (len(known.log.events), known.log.created):
            known = self._rebuilt(log)
        self._rooms[log.room] = known
        self._rooms.move_to_end(log.room)
        while len(self._rooms) > _MAX_ROOMS:
            self._rooms.popitem(last=False)
        return known

    def _rebuilt(self, log: Log) -> _Room:
        clock = _RoomClock(self._clock)
        clock.moment = _moment(log.created)
        service = CaseService(clock=clock, matcher=self._setup.matcher, executor=_AtOnce(), first_number=log.first)
        app = SandboxApp(service, self._auth, self._setup, clock, allowed_hosts=_EveryHost())
        for event in log.events:
            clock.moment = _moment(event.at)
            body = json.dumps(event.data).encode("utf-8")
            app.handle(Request("POST", event.path, _REPLAY_HEADERS, body, "replay"))
        clock.moment = None
        return _Room(app, clock, log)
