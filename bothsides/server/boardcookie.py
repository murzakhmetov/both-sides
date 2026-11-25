"""What happened on one visitor's board, as signed cookies. Any running copy of the server can read it."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import zlib
from dataclasses import dataclass, replace
from typing import Any

from ..demo.scenes import SCENES

COOKIE = "bs_board"
#: A board on which nothing has happened yet. It never takes the place of the one above.
SEED = "bs_new"
#: One action each. Two replies of two running copies may come in any order: the later one
#: takes the place of the board, but not of the other action.
ACTION = "bs_act"
_SLOTS = (*"012345", "c")
#: Two actions that follow each other at a human pace get two cookies.
_PACE_MILLISECONDS = 250
#: All cookies together stay under 16 KB, the most that hosts take in one header.
_PARTS = 2
_PART_LENGTH = 3600
_MAX_EVENTS = 300
_MAX_PLAIN = 64 * 1024
_SIGNATURE_BYTES = 16
_ROOM = re.compile(r"[A-Za-z0-9_-]{16,64}")
_START = re.compile(r"/api/scenes/([a-z]+)/start")
_RESET = "/api/reset"
_STORY = "/api/phone/sender/answer"
_CASE = re.compile(r"BS-\d+-(\d+)")
MAX_AGE_SECONDS = 2 * 60 * 60


@dataclass(frozen=True, slots=True)
class Event:
    """One accepted action: when (milliseconds), where, with which fields, and the comparison it led to."""

    at: int
    path: str
    data: dict[str, str]
    match: tuple[Any, ...] | None = None

    @property
    def key(self) -> tuple[Any, ...]:
        """The same on every running copy."""
        return (self.at, self.path, tuple(sorted(self.data.items())))

    @property
    def scene(self) -> str:
        """The scene that this action opens, or an empty text."""
        found = _START.fullmatch(self.path)
        return found.group(1) if found else ""

    @property
    def case(self) -> int:
        """The number of the case that this action is about, or 0."""
        found = _CASE.search(self.data.get("case_id", "") or self.path)
        return int(found.group(1)) if found else 0


@dataclass(frozen=True, slots=True)
class Log:
    """The life of one board: when it was created, its first number, and what happened after that."""

    room: str
    created: int
    first: int
    events: tuple[Event, ...] = ()

    @property
    def last(self) -> int:
        """The time of the last action."""
        return self.events[-1].at if self.events else self.created

    def with_event(self, event: Event) -> "Log":
        """Return the log with one more event."""
        return self.merged(replace(self, events=(event,)))

    def merged(self, other: "Log") -> "Log":
        """Return everything that both know, in the order of time.

        Two running copies may each have seen an action that the other one has not. The log
        that was cut later says where the board begins.
        """
        if self == other:
            return self
        base = self if self.created >= other.created else other
        known = {event.key: event for event in (*other.events, *self.events) if event.at > base.created}
        return replace(base, events=tuple(sorted(known.values(), key=lambda event: event.key)))

    def from_reset(self, background: int) -> "Log":
        """Return the log from the last reset on. The board is the same.

        *background* is how many numbers the seeded cases of a new board take.
        """
        resets = [index for index, event in enumerate(self.events) if event.path == _RESET]
        if not resets:
            return self
        before, after = self.events[: resets[-1]], self.events[resets[-1] + 1 :]
        return replace(self, created=self.events[resets[-1]].at, first=self._next_number(before, background), events=after)

    def _next_number(self, events: tuple[Event, ...], background: int) -> int:
        taken = sum(background + 1 if event.path == _RESET else bool(event.scene) for event in events)
        return self.first + background + 1 + taken

    def without_forgotten(self, background: int) -> "Log":
        """Return the log without what a later run of the same scene has wiped out. The board is the same.

        The starts stay, because they count the numbers. A story stays if the decision of a case
        that is still on the board was made while it was known. For a log without a reset.
        """
        number = self.first + background
        latest, ended = {SCENES[0].id: number}, {}
        for index, event in enumerate(self.events):
            if event.scene:
                number += 1
                if event.scene in latest:
                    ended[latest[event.scene]] = index
                latest[event.scene] = number
        told = {event.case: index for index, event in enumerate(self.events) if event.path == _STORY}
        decided = [told[case] for case in latest.values() if case in told]
        forgotten = {
            case for case, end in ended.items() if case not in told or not any(told[case] < index < end for index in decided)
        }
        return replace(self, events=tuple(event for event in self.events if event.scene or event.case not in forgotten))

    def from_last_start(self, background: int) -> "Log":
        """Return a much shorter log: the board begins anew with the last scene that was opened."""
        starts = [index for index, event in enumerate(self.events) if event.path.endswith(("/start", _RESET))]
        if not starts or starts[-1] == 0:
            return replace(self, events=(*self.events[:1], *self.events[1:][-20:]))
        dropped, kept = self.events[: starts[-1]], self.events[starts[-1] :]
        used = self._next_number(dropped, background) - self._next_number((), background)
        return replace(self, created=kept[0].at - 1, first=self.first + used, events=kept)


def _sign(secret: bytes, data: bytes) -> bytes:
    return hmac.new(secret, data, hashlib.sha256).digest()[:_SIGNATURE_BYTES]


def _raw(event: Event) -> list[Any]:
    return [event.at, event.path, event.data, *([] if event.match is None else [list(event.match)])]


def _plain(log: Log) -> bytes:
    board = [log.room, log.created, log.first, [_raw(event) for event in log.events]]
    # A lone half of a surrogate pair is no text, but a phone may send it.
    return json.dumps(board, ensure_ascii=False, separators=(",", ":")).encode("utf-8", "surrogatepass")


def _pack(log: Log, secret: bytes) -> str:
    data = zlib.compress(_plain(log), 9)
    return base64.urlsafe_b64encode(_sign(secret, data) + data).decode("ascii").rstrip("=")


def _fits(log: Log, secret: bytes) -> bool:
    if len(log.events) > _MAX_EVENTS or len(_plain(log)) > _MAX_PLAIN:
        return False
    return len(_pack(log, secret)) <= _PARTS * _PART_LENGTH


def fitted(log: Log, secret: bytes, background: int) -> Log:
    """Return the log, shortened until it fits into the cookies."""
    for shorten in (Log.from_reset, Log.without_forgotten):
        if not _fits(log, secret):
            log = shorten(log, background)
    while not _fits(log, secret):
        shorter = log.from_last_start(background)
        log = shorter if len(shorter.events) < len(log.events) else replace(log, events=())
    return log


def _flags(secure: bool) -> str:
    return f"Path=/api; HttpOnly; SameSite=Lax{'; Secure' if secure else ''}"


def _slot(action: Event) -> str:
    """A comparison takes seconds, so it never shares a cookie with what happens meanwhile."""
    return "c" if action.match is not None else str(action.at // _PACE_MILLISECONDS % 6)


def cookies(log: Log, secret: bytes, secure: bool, action: Event | None = None) -> tuple[tuple[str, str], ...]:
    """The Set-Cookie headers of a log that fits, and of the action that was made just now."""
    if action is not None:
        alone = _pack(replace(log, events=(action,)), secret)
        own = ("Set-Cookie", f"{ACTION}{_slot(action)}={alone}; {_flags(secure)}; Max-Age={MAX_AGE_SECONDS}")
        return (*cookies(log, secret, secure), own)
    packed = _pack(log, secret)
    parts = [packed[i * _PART_LENGTH : (i + 1) * _PART_LENGTH] for i in range(_PARTS)]
    return tuple(
        ("Set-Cookie", f"{COOKIE}{i}={part}; {_flags(secure)}; Max-Age={MAX_AGE_SECONDS if part else 0}")
        for i, part in enumerate(parts)
    )


def seed_cookie(log: Log, secret: bytes, secure: bool) -> tuple[str, str]:
    """The Set-Cookie header for a visitor who has done nothing yet."""
    return ("Set-Cookie", f"{SEED}={_pack(replace(log, events=()), secret)}; {_flags(secure)}; Max-Age={MAX_AGE_SECONDS}")


def _event(raw: Any) -> Event:
    at, path, data, *rest = raw
    if not (isinstance(at, int) and isinstance(path, str) and isinstance(data, dict)):
        raise ValueError("no event")
    if not all(isinstance(value, str) for value in data.values()):
        raise ValueError("no event")
    return Event(at, path, data, tuple(rest[0]) if rest else None)


def _unpacked(packed: str, secret: bytes) -> Log | None:
    if not packed or len(packed) > _PARTS * _PART_LENGTH:
        return None
    try:
        raw = base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4))
        signature, data = raw[:_SIGNATURE_BYTES], raw[_SIGNATURE_BYTES:]
        if not hmac.compare_digest(signature, _sign(secret, data)):
            return None
        plain = zlib.decompressobj().decompress(data, _MAX_PLAIN)
        room, created, first, events = json.loads(plain.decode("utf-8", "surrogatepass"))
        if not (isinstance(room, str) and _ROOM.fullmatch(room) and isinstance(created, int) and isinstance(first, int)):
            return None
        return Log(room, created, first, tuple(_event(item) for item in events[:_MAX_EVENTS]))
    except (ValueError, TypeError, RecursionError, zlib.error):
        return None


def read(header: str, secret: bytes) -> Log | None:
    """Return the log of a Cookie header, or None when there is none that this server signed."""
    found = dict(part.strip().partition("=")[::2] for part in header.split(";"))
    board = _unpacked("".join(found.get(f"{COOKIE}{i}", "") for i in range(_PARTS)), secret)
    if board is None:
        return _unpacked(found.get(SEED, ""), secret)
    for slot in _SLOTS:
        action = _unpacked(found.get(f"{ACTION}{slot}", ""), secret)
        if action is not None and action.room == board.room:
            board = board.merged(action)
    return board
