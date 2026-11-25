"""A tiny client that talks to the app without sockets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bothsides.cases.service import CaseService
from bothsides.matching.factory import build_matcher
from bothsides.matching.types import Matcher
from bothsides.server.app import App
from bothsides.server.auth import StaffAuth
from bothsides.server.messages import Request, Response

from .fakes import InlineExecutor, ManualClock
from .helpers import START

PASSWORD = "unit-test-password"
HOST = "127.0.0.1:8000"
ORIGIN = f"http://{HOST}"
#: Few rounds keep the tests fast; the real number is checked on its own.
TEST_ITERATIONS = 1_000


def make_app(matcher: Matcher | None = None, web_root: Path | None = None) -> tuple[App, ManualClock]:
    clock = ManualClock(START)
    setup = build_matcher(offline=True, env={})
    service = CaseService(clock=clock, matcher=matcher or setup.matcher, executor=InlineExecutor())
    auth = StaffAuth(PASSWORD, clock=clock, iterations=TEST_ITERATIONS)
    app = App(service=service, auth=auth, setup=setup, clock=clock, web_root=web_root)
    return app, clock


class WebClient:
    """Keeps the session cookie between calls, like a browser."""

    def __init__(self, app: App, address: str = "127.0.0.1") -> None:
        self.app = app
        self.address = address
        self.cookie = ""

    def request(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> Response:
        merged = {"host": HOST, **({"cookie": self.cookie} if self.cookie else {}), **(headers or {})}
        response = self.app.handle(
            Request(method=method, target=path, headers=merged, body=body, address=self.address)
        )
        for name, value in response.headers:
            if name.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
        return response

    def get(self, path: str, **headers: str) -> Response:
        return self.request("GET", path, headers=headers)

    def post(self, path: str, data: Any = None, **headers: str) -> Response:
        merged = {"origin": ORIGIN, "content-type": "application/json", **headers}
        body = json.dumps(data if data is not None else {}).encode()
        return self.request("POST", path, body=body, headers=merged)

    def login(self, password: str = PASSWORD) -> Response:
        return self.post("/api/login", {"password": password})


def payload(response: Response) -> Any:
    return json.loads(response.body.decode("utf-8"))


def data(response: Response) -> Any:
    parsed = payload(response)
    assert parsed["success"] is True, parsed
    return parsed["data"]


def error(response: Response) -> str:
    parsed = payload(response)
    assert parsed["success"] is False, parsed
    return parsed["error"]


def header(response: Response, name: str) -> str:
    return next((value for key, value in response.headers if key.lower() == name.lower()), "")
