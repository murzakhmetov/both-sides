"""Every other /api/... address as one function on Vercel (vercel.json leads them here).

The whole app with one board per visitor. The offline matcher compares unless GEMINI_API_KEY
is set in the project settings on Vercel.
"""

from __future__ import annotations

import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bothsides import config  # noqa: E402
from bothsides.clock import SystemClock  # noqa: E402
from bothsides.matching.factory import build_matcher  # noqa: E402
from bothsides.server.budget import Budget  # noqa: E402
from bothsides.server.messages import Request, Response, error_response  # noqa: E402
from bothsides.server.online import OnlineApp  # noqa: E402
from bothsides.server.security import SECURITY_HEADERS  # noqa: E402

#: The same in every running copy of one deployment; unknown outside of the account.
_SECRET = (os.environ.get("VERCEL_DEPLOYMENT_ID") or os.environ.get("VERCEL_URL") or secrets.token_hex(16)).encode("utf-8")
_CLOCK = SystemClock()
_BUDGET = Budget(_CLOCK)
_SETUP = build_matcher(False, os.environ, may_ask=_BUDGET.may_ask)
_APP = OnlineApp(_SETUP, _CLOCK, _SECRET, _BUDGET)


def _target(raw: str) -> str:
    """The address the visitor asked for, whether or not the platform kept it."""
    parts = urlsplit(raw)
    if parts.path.rstrip("/") != "/api/app":
        return parts.path
    asked = parse_qs(parts.query).get("p", [""])[0]
    return f"/api/{asked.lstrip('/')}"


class handler(BaseHTTPRequestHandler):  # noqa: N801  (Vercel looks for this name)
    """One request. Vercel sets the address and the host of the visitor in its own headers."""

    server_version = "BothSides"
    sys_version = ""

    def _header(self, name: str, fallback: str) -> str:
        return (self.headers.get(name) or fallback).split(",", 1)[0].strip()

    def _length(self) -> int | None:
        raw = self.headers.get("Content-Length") or ""
        return int(raw) if raw.isascii() and raw.isdigit() and len(raw) <= 9 else None

    def _request(self, body: bytes) -> Request:
        headers = {name.lower(): value for name, value in self.headers.items()}
        host = self._header("x-forwarded-host", headers.get("host", ""))
        address = self._header("x-real-ip", self.client_address[0])
        return Request(self.command, _target(self.path), {**headers, "host": host}, body, address)

    def _answer(self) -> None:
        length = self._length() if self.command == "POST" else 0
        if length is None:
            self._send(error_response(411, "length_required").with_headers(*SECURITY_HEADERS))
        elif length > config.MAX_BODY_BYTES:
            self.rfile.read(min(length, config.MAX_REQUEST_BYTES))
            self._send(error_response(413, "too_large").with_headers(*SECURITY_HEADERS))
        else:
            request = self._request(self.rfile.read(length))
            if request.path == "/api/status":
                _SETUP.confirm_model_now()
            self._send(_APP.handle(request))

    def _send(self, response: Response) -> None:
        self.send_response(response.status)
        for name, value in response.headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _answer

    def log_message(self, format: str, *args: object) -> None:
        """Nothing about a visitor goes to the log."""
