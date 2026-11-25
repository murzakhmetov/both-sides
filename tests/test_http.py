"""Every demo scene end to end over a real local HTTP connection."""

from __future__ import annotations

import http.client
import json
import socket
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from bothsides.matching.types import Tri
from bothsides.server.http import make_server

from .fakes import StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER, as_json
from .webclient import PASSWORD, make_app


class Browser:
    """Speaks real HTTP with a cookie and an Origin header."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.cookie = ""

    def call(self, method: str, path: str, data: Any = None) -> tuple[int, Any]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Cookie": self.cookie} if self.cookie else {}
        body = None
        if method == "POST":
            body = json.dumps(data or {}).encode()
            headers |= {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        cookie = response.getheader("Set-Cookie")
        if cookie:
            self.cookie = cookie.split(";", 1)[0]
        connection.close()
        return response.status, json.loads(text)

    def data(self, method: str, path: str, data: Any = None) -> Any:
        status, body = self.call(method, path, data)
        assert status == 200, (path, body)
        return body["data"]


def serve(matcher: object = None) -> Iterator[Browser]:
    app, _ = make_app(matcher)  # type: ignore[arg-type]
    server = make_server(app, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Browser(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def offline() -> Iterator[Browser]:
    yield from serve()


@pytest.fixture
def with_model() -> Iterator[Browser]:
    yield from serve(StubMatcher(gemini_result(0.03, Tri.FALSE, Tri.FALSE)))


def choose(browser: Browser, scene: str) -> str:
    browser.data("POST", "/api/login", {"password": PASSWORD})
    browser.data("POST", f"/api/scenes/{scene}/start")
    return browser.data("GET", "/api/phone/receiver")["case_id"]


def answer_both(browser: Browser, number: str, receiver: str, sender: str) -> None:
    browser.data("POST", "/api/phone/receiver/answer", {"case_id": number, "text": receiver})
    browser.data("POST", "/api/phone/sender/answer", {"case_id": number, "text": sender})


def test_scene_one_is_credited(offline: Browser) -> None:
    number = choose(offline, "brother")
    answer_both(offline, number, BROTHER_RECEIVER, BROTHER_SENDER)
    stage = offline.data("GET", "/api/stage")
    assert stage["case"]["state"] == "credited"
    assert stage["case"]["match"]["probability"] >= 0.8
    assert stage["seconds"] is not None
    for side in ("receiver", "sender"):
        phone = offline.data("GET", f"/api/phone/{side}")
        assert phone["status"] == "credited"
        assert "probability" not in as_json(phone)


def test_scene_two_goes_to_a_person_offline(offline: Browser) -> None:
    number = choose(offline, "sister")
    answer_both(offline, number, SISTER_RECEIVER, SISTER_SENDER)
    file = offline.data("GET", f"/api/cases/{number}")
    assert file["state"] == "with_specialist"
    assert file["receiver_answer"]["text"] == SISTER_RECEIVER
    assert file["sender_answer"]["text"] == SISTER_SENDER
    assert file["deadline_at"].startswith("2026-12-03")


def test_scene_two_is_held_with_the_language_model(with_model: Browser) -> None:
    number = choose(with_model, "sister")
    answer_both(with_model, number, SISTER_RECEIVER, SISTER_SENDER)
    assert with_model.data("GET", "/api/phone/sender")["status"] == "held"
    assert with_model.data("POST", f"/api/cases/{number}/return")["state"] == "returned"
    assert with_model.data("GET", "/api/phone/receiver")["status"] == "returned"


def test_scene_three_offers_a_return(offline: Browser) -> None:
    number = choose(offline, "stranger")
    offline.data("POST", "/api/phone/receiver/deny", {"case_id": number})
    view = offline.data("POST", "/api/phone/receiver/deny", {"case_id": number})
    assert (view["status"], view["case_number"]) == ("return_offer", number)
    assert offline.data("GET", "/api/phone/sender")["status"] == "question"
    offline.data("POST", "/api/phone/sender/answer", {"case_id": number, "text": "оплата за товар с сайта"})
    assert offline.data("GET", "/api/phone/sender")["status"] == "with_specialist"
    assert offline.data("POST", "/api/phone/receiver/accept-return", {"case_id": number})["status"] == "returned"


def test_scene_one_three_times_in_a_row(offline: Browser) -> None:
    for _ in range(3):
        number = choose(offline, "brother")
        answer_both(offline, number, BROTHER_RECEIVER, BROTHER_SENDER)
        assert offline.data("GET", "/api/phone/sender")["status"] == "credited"


@pytest.mark.parametrize("text", ["asdf qwer", "спасибо большое", "бәрі жақсы рахмет"])
def test_nonsense_never_passes(offline: Browser, text: str) -> None:
    number = choose(offline, "brother")
    answer_both(offline, number, text, text)
    assert offline.data("GET", "/api/phone/receiver")["status"] == "with_specialist"


def raw(port: int, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall(request)
        chunks = []
        while chunk := connection.recv(4096):
            chunks.append(chunk)
    return b"".join(chunks)


def head_of(reply: bytes) -> str:
    return reply.split(b"\r\n\r\n")[0].decode("latin-1").lower()


def test_head_tells_the_length_and_sends_no_body(offline: Browser) -> None:
    host = f"Host: 127.0.0.1:{offline.port}\r\nConnection: close\r\n\r\n"
    get = raw(offline.port, f"GET /api/status HTTP/1.1\r\n{host}".encode())
    head = raw(offline.port, f"HEAD /api/status HTTP/1.1\r\n{host}".encode())
    length = len(get.split(b"\r\n\r\n", 1)[1])
    assert f"content-length: {length}" in head_of(head)
    assert head.split(b"\r\n\r\n", 1)[1] == b""


@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT", "DELETE", "OPTIONS"])
def test_a_body_is_never_taken_for_the_next_request(offline: Browser, method: str) -> None:
    inner = f"GET /api/session HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\n\r\n"
    outer = (
        f"{method} /api/status HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\n"
        f"Content-Length: {len(inner)}\r\n\r\n{inner}"
    )
    assert raw(offline.port, outer.encode()).count(b"HTTP/1.1 ") == 1


@pytest.mark.parametrize(
    "lengths",
    ["Content-Length: 2\r\nContent-Length: 100\r\n", "Transfer-Encoding:\r\nTransfer-Encoding: chunked\r\n"],
)
def test_two_lengths_are_refused(offline: Browser, lengths: str) -> None:
    request = (
        f"POST /api/login HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\nOrigin: http://127.0.0.1:{offline.port}\r\n"
        f"Content-Type: application/json\r\n{lengths}\r\n{{}}"
    )
    status = raw(offline.port, request.encode()).split(b"\r\n")[0]
    assert b"400" in status or b"411" in status


def test_dripping_client_is_cut_off_and_others_are_served(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from bothsides import config

    monkeypatch.setattr(config, "REQUEST_SECONDS", 1.0)
    for browser in serve():
        with socket.create_connection(("127.0.0.1", browser.port), timeout=10) as slow:
            started = time.monotonic()
            closed = False
            slow.sendall(b"GET /api/status HTTP/1.1\r\nX: ")
            while time.monotonic() - started < 5 and not closed:
                time.sleep(0.2)
                assert browser.data("GET", "/api/status")
                try:
                    slow.sendall(b"a")
                    slow.settimeout(0.01)
                    closed = slow.recv(1) == b""
                except TimeoutError:
                    continue
                except OSError:
                    closed = True
            assert closed
            assert time.monotonic() - started < 4


def test_one_address_cannot_take_every_connection() -> None:
    from bothsides import config
    from bothsides.server.http import Server

    app, _ = make_app()
    server = make_server(app, "127.0.0.1", 0)
    try:
        taken = [Server._take_slot(server, "10.0.0.66") for _ in range(200)]
        assert taken.count(True) == config.MAX_CONNECTIONS_PER_ADDRESS
        assert Server._take_slot(server, "10.0.0.5")
        Server._free_slot(server, "10.0.0.66")
        assert Server._take_slot(server, "10.0.0.66")
    finally:
        server.server_close()


def test_endless_headers_are_cut_off(offline: Browser) -> None:
    request = f"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\n"
    request += "".join(f"X-{i}: {'a' * 8000}\r\n" for i in range(40)) + "\r\n"
    try:
        reply = raw(offline.port, request.encode())
    except OSError:
        reply = b""
    assert b"200" not in reply.split(b"\r\n")[0]
    assert offline.data("GET", "/api/status")


@pytest.mark.parametrize(("first", "second"), [("0.0.0.0", "127.0.0.1"), ("127.0.0.1", "0.0.0.0"), ("127.0.0.1", "127.0.0.1")])
def test_a_second_server_cannot_share_the_port(first: str, second: str) -> None:
    app, _ = make_app()
    server = make_server(app, first, 0)
    try:
        with pytest.raises(OSError):
            make_server(app, second, server.server_address[1])
    finally:
        server.server_close()


def test_server_header_hides_the_software(offline: Browser) -> None:
    reply = raw(offline.port, f"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\nConnection: close\r\n\r\n".encode())
    head = reply.split(b"\r\n\r\n")[0].lower()
    assert b"python" not in head and b"basehttp" not in head


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ("Content-Length: 999999\r\n", b"413"),
        ("Content-Length: -5\r\n", b"400"),
        ("Content-Length: abc\r\n", b"400"),
        ("Transfer-Encoding: chunked\r\n", b"411"),
        ("", b"411"),
    ],
)
def test_bad_lengths(offline: Browser, headers: str, status: bytes) -> None:
    request = (
        f"POST /api/login HTTP/1.1\r\nHost: 127.0.0.1:{offline.port}\r\n"
        f"Origin: http://127.0.0.1:{offline.port}\r\nContent-Type: application/json\r\n{headers}Connection: close\r\n\r\n"
    )
    assert status in raw(offline.port, request.encode()).split(b"\r\n")[0]


def test_garbage_does_not_stop_the_server(offline: Browser) -> None:
    raw(offline.port, b"\x16\x03\x01\x02\x00\x01\x00\r\n\r\n")
    raw(offline.port, b"GET / HTTP/1.1\r\nHost: \xff\xfe\r\nConnection: close\r\n\r\n")
    assert offline.data("GET", "/api/status")["matcher"]["active"] == "offline"


def test_access_log_has_no_query_or_body(offline: Browser, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    offline.call("GET", "/api/status?token=do-not-log")
    offline.call("POST", "/api/login", {"password": "do-not-log-this-either"})
    assert "/api/status" in caplog.text
    assert "do-not-log" not in caplog.text
