"""Connects the app to real sockets with the standard library."""

from __future__ import annotations

import io
import logging
import socket
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .. import config
from .app import App
from .messages import Request, Response, error_response
from .security import SECURITY_HEADERS

_LOG = logging.getLogger(__name__)


class _BadLength(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


class _RequestTooLarge(OSError):
    """The client sent more header or body bytes than any request needs."""


class _LimitedReader(io.RawIOBase):
    """Reads from a socket with a total deadline and a byte limit per request.

    The plain socket timeout starts again with every byte, so a client that
    drips bytes could hold a connection for ever.
    """

    def __init__(self, connection: socket.socket) -> None:
        super().__init__()
        self._connection = connection
        self._deadline = 0.0
        self._left = 0

    def start_request(self) -> None:
        self._deadline = time.monotonic() + config.REQUEST_SECONDS
        self._left = config.MAX_REQUEST_BYTES

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("the request took too long")
        if self._left <= 0:
            raise _RequestTooLarge("the request is too large")
        self._connection.settimeout(remaining)
        count = self._connection.recv_into(memoryview(buffer)[: self._left])
        self._left -= count
        return count


class Server(ThreadingHTTPServer):
    """One thread per connection, with a ceiling in total and per address."""

    daemon_threads = True
    request_queue_size = config.MAX_CONNECTIONS
    #: On Windows "reuse" would let a second server take the same port silently.
    allow_reuse_address = not sys.platform.startswith("win")

    def __init__(self, address: tuple[str, int], app: App) -> None:
        self.app = app
        self._open: Counter[str] = Counter()
        self._open_lock = threading.Lock()
        super().__init__(address, _Handler)

    def server_bind(self) -> None:
        # Without this, Windows lets 127.0.0.1 and 0.0.0.0 share one port.
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        super().server_bind()

    def _take_slot(self, address: str) -> bool:
        with self._open_lock:
            if self._open.total() >= config.MAX_CONNECTIONS:
                return False
            if self._open[address] >= config.MAX_CONNECTIONS_PER_ADDRESS:
                return False
            self._open[address] += 1
            return True

    def _free_slot(self, address: str) -> None:
        with self._open_lock:
            self._open[address] -= 1
            if self._open[address] <= 0:
                del self._open[address]

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._take_slot(client_address[0]):
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._free_slot(client_address[0])

    def handle_error(self, request: Any, client_address: Any) -> None:
        # Broken connections are normal when a phone sleeps; no stack traces.
        _LOG.info("connection closed: %s", type(sys.exc_info()[1]).__name__)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BothSides"
    sys_version = ""
    #: For writing; reading has its own total deadline.
    timeout = config.REQUEST_SECONDS
    server: Server

    def setup(self) -> None:
        super().setup()
        self._reader = _LimitedReader(self.connection)
        self.rfile = io.BufferedReader(self._reader)  # type: ignore[assignment]

    def handle_one_request(self) -> None:
        self._reader.start_request()
        super().handle_one_request()

    def _has_body_headers(self) -> bool:
        return bool(self.headers.get_all("Content-Length") or self.headers.get_all("Transfer-Encoding"))

    def _body_length(self) -> int:
        if self.headers.get_all("Transfer-Encoding"):
            raise _BadLength(411, "length_required")
        lengths = self.headers.get_all("Content-Length") or []
        if not lengths:
            raise _BadLength(411, "length_required")
        raw = lengths[0]
        if len(lengths) > 1 or not (raw.isascii() and raw.isdigit()):
            raise _BadLength(400, "bad_length")
        if len(raw) > 9 or int(raw) > config.MAX_BODY_BYTES:
            raise _BadLength(413, "too_large")
        return int(raw)

    def _read_request(self) -> Request:
        body = b""
        if self.command == "POST":
            body = self.rfile.read(self._body_length())
        elif self._has_body_headers():
            # An unread body must never be taken for the next request.
            self.close_connection = True
        headers = {name.lower(): value for name, value in self.headers.items()}
        return Request(self.command, self.path, headers, body, self.client_address[0])

    def _answer(self) -> None:
        try:
            response = self.server.app.handle(self._read_request())
        except _BadLength as error:
            # The body was not read, so this connection cannot be used again.
            self.close_connection = True
            response = error_response(error.status, error.code).with_headers(*SECURITY_HEADERS)
        self._send(response)

    def _send(self, response: Response) -> None:
        self.connection.settimeout(self.timeout)
        self.send_response(response.status)
        for name, value in response.headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response.body)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)

    do_GET = do_HEAD = do_POST = _answer
    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_TRACE = _answer

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """Replace the standard HTML error page with the common envelope."""
        self.close_connection = True
        try:
            self._send(error_response(code, "bad_request").with_headers(*SECURITY_HEADERS))
        except (OSError, AttributeError):
            return

    def log_request(self, code: Any = "-", size: Any = "-") -> None:
        path = getattr(self, "path", "-").split("?", 1)[0]
        _LOG.info("%s %s %s", getattr(self, "command", "-"), path, int(code) if str(code).isdigit() else code)

    def log_message(self, format: str, *args: Any) -> None:
        _LOG.debug("http: %s", type(args).__name__)


def make_server(app: App, host: str, port: int) -> Server:
    """Open the port. Raises OSError when it is taken."""
    return Server((host, port), app)


def private_addresses() -> tuple[str, ...]:
    """Addresses of this laptop on the local network. Sends nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 9))
            return (probe.getsockname()[0],)
    except OSError:
        return ()
