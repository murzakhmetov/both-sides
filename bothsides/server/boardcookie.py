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

COOKIE = "bs_board"
_PARTS = 3
_PART_LENGTH = 3600
_MAX_EVENTS = 80
_MAX_PLAIN = 64 * 1024
_SIGNATURE_BYTES = 16
_ROOM = re.compile(r"[A-Za-z0-9_-]{16,64}")
MAX_AGE_SECONDS = 2 * 60 * 60


@dataclass(frozen=True, slots=True)
class Event:
    """One accepted action: when (milliseconds), where, with which fields, and the comparison it led to."""

    at: int
    path: str
    data: dict[str, Any]
    match: tuple[Any, ...] | None = None


@dataclass(frozen=True, slots=True)
class Log:
    """The life of one board."""

    room: str
    created: int
    first: int
    events: tuple[Event, ...] = ()

    def with_event(self, event: Event) -> "Log":
        """Return the log with one more event, in the order of time: a slow one may end after a later one."""
        return replace(self, events=tuple(sorted((*self.events, event), key=lambda known: known.at)))

    def from_last_start(self, background: int) -> "Log":
        """Return a shorter log: the board begins anew with the last scene that was opened.

        *background* is how many numbers the seeded cases of a new board take, so that the
        case keeps its number.
        """
        starts = [i for i, event in enumerate(self.events) if event.path.endswith(("/start", "/reset"))]
        if not starts or starts[-1] == 0:
            return replace(self, events=(*self.events[:1], *self.events[1:][-20:]))
        dropped, kept = self.events[: starts[-1]], self.events[starts[-1] :]
        used = sum(1 if event.path.endswith("/start") else background + 1 for event in dropped if event.path.endswith(("/start", "/reset")))
        return replace(self, created=kept[0].at, first=self.first + used, events=kept)


def _sign(secret: bytes, data: bytes) -> bytes:
    return hmac.new(secret, data, hashlib.sha256).digest()[:_SIGNATURE_BYTES]


def _raw(event: Event) -> list[Any]:
    return [event.at, event.path, event.data, *([] if event.match is None else [list(event.match)])]


def _pack(log: Log, secret: bytes) -> str:
    board = [log.room, log.created, log.first, [_raw(event) for event in log.events]]
    plain = json.dumps(board, ensure_ascii=False, separators=(",", ":"))
    data = zlib.compress(plain.encode("utf-8"), 9)
    return base64.urlsafe_b64encode(_sign(secret, data) + data).decode("ascii").rstrip("=")


def fitted(log: Log, secret: bytes, background: int) -> Log:
    """Return the log, shortened until it fits into the cookies."""
    while len(log.events) > _MAX_EVENTS or len(_pack(log, secret)) > _PARTS * _PART_LENGTH:
        shorter = log.from_last_start(background)
        log = shorter if len(shorter.events) < len(log.events) else replace(log, events=())
    return log


def cookies(log: Log, secret: bytes, secure: bool) -> tuple[tuple[str, str], ...]:
    """The Set-Cookie headers of a log that fits."""
    packed = _pack(log, secret)
    flags = f"Path=/api; HttpOnly; SameSite=Lax{'; Secure' if secure else ''}"
    parts = [packed[i * _PART_LENGTH : (i + 1) * _PART_LENGTH] for i in range(_PARTS)]
    return tuple(
        ("Set-Cookie", f"{COOKIE}{i}={part}; {flags}; Max-Age={MAX_AGE_SECONDS if part else 0}")
        for i, part in enumerate(parts)
    )


def _event(raw: Any) -> Event:
    at, path, data, *rest = raw
    if not (isinstance(at, int) and isinstance(path, str) and isinstance(data, dict)):
        raise ValueError("no event")
    return Event(at, path, data, tuple(rest[0]) if rest else None)


def read(header: str, secret: bytes) -> Log | None:
    """Return the log of a Cookie header, or None when there is none that this server signed."""
    found = dict(part.strip().partition("=")[::2] for part in header.split(";"))
    packed = "".join(found.get(f"{COOKIE}{i}", "") for i in range(_PARTS))
    if not packed or len(packed) > _PARTS * _PART_LENGTH:
        return None
    try:
        raw = base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4))
        signature, data = raw[:_SIGNATURE_BYTES], raw[_SIGNATURE_BYTES:]
        if not hmac.compare_digest(signature, _sign(secret, data)):
            return None
        plain = zlib.decompressobj().decompress(data, _MAX_PLAIN)
        room, created, first, events = json.loads(plain.decode("utf-8"))
        if not (isinstance(room, str) and _ROOM.fullmatch(room) and isinstance(created, int) and isinstance(first, int)):
            return None
        return Log(room, created, first, tuple(_event(item) for item in events[:_MAX_EVENTS]))
    except (ValueError, TypeError, zlib.error):
        return None
