"""Requests, responses and JSON helpers of the small web app."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

Headers = tuple[tuple[str, str], ...]

#: JSON stays valid and no user text can open a tag in any browser.
_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", " ": "\\u2028", " ": "\\u2029"}


@dataclass(frozen=True, slots=True)
class Request:
    """One HTTP request. Header names are lower case."""

    method: str
    target: str
    headers: dict[str, str]
    body: bytes
    address: str

    @property
    def path(self) -> str:
        """The path without the query string."""
        return self.target.split("?", 1)[0].split("#", 1)[0]


@dataclass(frozen=True, slots=True)
class Response:
    """One HTTP response."""

    status: int
    headers: Headers
    body: bytes

    def with_headers(self, *extra: tuple[str, str]) -> "Response":
        """Return a copy with more headers; a name that is already set wins."""
        known = {name.lower() for name, _ in self.headers}
        added = tuple((name, value) for name, value in extra if name.lower() not in known)
        return replace(self, headers=(*self.headers, *added))


class HttpError(Exception):
    """Stops a request with a status and a code that is safe to show."""

    def __init__(self, status: int, code: str, headers: Headers = ()) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.headers = headers


def to_json(value: Any) -> bytes:
    """Encode as JSON with markup characters escaped."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in _ESCAPES.items():
        text = text.replace(char, escaped)
    return text.encode("utf-8")


def json_response(data: Any, status: int = 200, headers: Headers = ()) -> Response:
    """Wrap data in the common envelope."""
    return Response(
        status=status,
        headers=(("Content-Type", "application/json; charset=utf-8"), *headers),
        body=to_json({"success": True, "data": data}),
    )


def error_response(status: int, code: str, headers: Headers = ()) -> Response:
    """Wrap an error code in the common envelope."""
    return Response(
        status=status,
        headers=(("Content-Type", "application/json; charset=utf-8"), *headers),
        body=to_json({"success": False, "error": code}),
    )


def text_response(status: int, text: str) -> Response:
    """Plain text for people who open a page that cannot be shown."""
    return Response(status, (("Content-Type", "text/plain; charset=utf-8"),), text.encode("utf-8"))


def redirect(status: int, location: str) -> Response:
    """Send the browser to another page of this app."""
    return Response(status, (("Location", location),), b"")
