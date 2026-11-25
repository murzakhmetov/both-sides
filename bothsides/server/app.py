"""The web app without sockets: a request goes in, a response comes out."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .. import config
from ..cases.errors import ServiceError
from ..cases.service import CaseService
from ..clock import Clock
from ..matching.factory import MatcherSetup
from .auth import StaffAuth
from . import static
from .messages import HttpError, Request, Response, error_response, redirect
from .ratelimit import RateLimiter
from .routes import SESSION_COOKIE, Context, Route, find_route
from .security import SECURITY_HEADERS, host_allowed, origin_allowed

_LOG = logging.getLogger(__name__)

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
_METHODS = frozenset({"GET", "HEAD", "POST"})
_PAGES = frozenset({"/start", "/receiver", "/sender", "/login", "/stage", "/console", "/demo"})


class App:
    """Checks every request and calls the right handler."""

    def __init__(
        self,
        service: CaseService,
        auth: StaffAuth,
        setup: MatcherSetup,
        clock: Clock,
        web_root: Path | None = None,
        allowed_hosts: frozenset[str] = frozenset(),
    ) -> None:
        self.service = service
        self.auth = auth
        self.setup = setup
        self.web_root = web_root or WEB_ROOT
        self._clock = clock
        self._allowed_hosts = allowed_hosts
        self._pages = RateLimiter(config.RATE_LIMIT_PAGES, config.RATE_WINDOW)
        self._reads = RateLimiter(config.RATE_LIMIT_READS, config.RATE_WINDOW)
        self._writes = RateLimiter(config.RATE_LIMIT_WRITES, config.RATE_WINDOW)
        self._logins = RateLimiter(config.RATE_LIMIT_LOGIN, config.RATE_WINDOW)
        self._tries = RateLimiter(config.RATE_LIMIT_TRY, config.RATE_WINDOW)

    def handle(self, request: Request) -> Response:
        """Answer one request. Never raises."""
        try:
            response = self._dispatch(request)
        except HttpError as error:
            response = self._error(request, error)
        except ServiceError as error:
            response = error_response(error.status, error.code)
        except Exception as error:
            # The message may hold user text, so only the class name is logged.
            _LOG.error("request failed: %s", type(error).__name__)
            response = error_response(500, "server_error")
        return response.with_headers(*SECURITY_HEADERS)

    def _error(self, request: Request, error: HttpError) -> Response:
        """A person who mistypes an address gets a page, a program gets JSON."""
        path = request.path
        is_page = request.method in {"GET", "HEAD"} and not path.startswith(("/api/", "/assets/"))
        if error.status != 404 or not is_page or len(path) > config.MAX_PATH_LENGTH:
            return error_response(error.status, error.code, error.headers)
        if path.rstrip("/") in _PAGES:
            return redirect(302, path.rstrip("/"))
        return static.page(self.web_root, "app.html", status=404)

    # -- session ----------------------------------------------------------------

    def session_token(self, request: Request) -> str:
        """Return the session token of the cookie, or an empty text.

        A plain split: the standard cookie parser drops the whole header at the
        first unusual cookie of another local app, and is slow on long ones.
        """
        for part in request.headers.get("cookie", "").split(";"):
            name, _, value = part.partition("=")
            if name.strip() == SESSION_COOKIE:
                return value.strip()
        return ""

    def is_staff(self, request: Request) -> bool:
        """True when the request carries a valid staff session."""
        return self.auth.is_valid(self.session_token(request))

    # -- checks -------------------------------------------------------------------

    def _dispatch(self, request: Request) -> Response:
        if not host_allowed(request.headers.get("host", ""), self._allowed_hosts):
            raise HttpError(421, "bad_host")
        if request.method not in _METHODS:
            raise HttpError(405, "bad_method", (("Allow", "GET, HEAD, POST"),))
        method = "GET" if request.method == "HEAD" else request.method
        # Before counting: another site must not spend this visitor's limit.
        self._check_source(request, method)
        self._check_rate(request, method)
        if len(request.path) > config.MAX_PATH_LENGTH:
            raise HttpError(404, "not_found")
        route, params = find_route(method, request.path)
        data = self._read_body(request) if method == "POST" else {}
        if route.staff and not self.is_staff(request):
            return self._ask_for_login(request, route)
        return route.handler(Context(self, request, params, data))

    @staticmethod
    def _check_source(request: Request, method: str) -> None:
        if method == "POST":
            if not origin_allowed(request.headers.get("origin", ""), request.headers.get("host", "")):
                raise HttpError(403, "bad_origin")
        elif request.path.startswith("/api/") and request.headers.get("sec-fetch-site") == "cross-site":
            raise HttpError(403, "bad_origin")

    def _check_rate(self, request: Request, method: str) -> None:
        if method == "GET":
            # Any site may load a page, so pages must not use up the polling of the phones.
            limiter = self._reads if request.path.startswith("/api/") else self._pages
        elif request.path == "/api/login":
            limiter = self._logins
        elif request.path == "/api/try":
            limiter = self._tries
        else:
            limiter = self._writes
        wait = limiter.wait_seconds(request.address, self._clock.now())
        if wait > 0:
            raise HttpError(429, "rate_limited", (("Retry-After", str(wait)),))

    @staticmethod
    def _read_body(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise HttpError(415, "bad_content_type")
        if len(request.body) > config.MAX_BODY_BYTES:
            raise HttpError(413, "too_large")
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (ValueError, RecursionError):
            raise HttpError(400, "bad_json") from None
        if not isinstance(data, dict):
            raise HttpError(400, "bad_json")
        return data

    @staticmethod
    def _ask_for_login(request: Request, route: Route) -> Response:
        if route.page:
            return redirect(303, f"/login?next={request.path}")
        raise HttpError(401, "login_required")
