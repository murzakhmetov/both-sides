"""The mini-demo alone, for a host that keeps nothing between requests (a function on Vercel).

The full app needs one running process: cases, staff sessions and limits live in its memory.
"""

from __future__ import annotations

import logging
from typing import Any

from .. import config
from ..cases.errors import ServiceError
from ..cases.tryout import try_answers
from ..clock import Clock
from .app import App
from .messages import HttpError, Request, Response, error_response, json_response
from .ratelimit import RateLimiter
from .security import SECURITY_HEADERS

_LOG = logging.getLogger(__name__)


def _field(data: dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise HttpError(400, "bad_field")
    return value


class TryApp:
    """Answers POST /api/try with the checks of the app, and nothing else."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        # Per running instance only: a host that starts several of them counts in each.
        self._tries = RateLimiter(config.RATE_LIMIT_TRY, config.RATE_WINDOW)

    def handle(self, request: Request) -> Response:
        """Answer one request. Never raises."""
        try:
            response = self._answer(request)
        except HttpError as error:
            response = error_response(error.status, error.code, error.headers)
        except ServiceError as error:
            response = error_response(error.status, error.code)
        except Exception as error:
            # The message may hold user text, so only the class name is logged.
            _LOG.error("request failed: %s", type(error).__name__)
            response = error_response(500, "server_error")
        return response.with_headers(*SECURITY_HEADERS)

    def _answer(self, request: Request) -> Response:
        if request.method != "POST":
            raise HttpError(405, "bad_method", (("Allow", "POST"),))
        # Before counting: another site must not spend this visitor's limit.
        App._check_source(request, "POST")
        wait = self._tries.wait_seconds(request.address, self._clock.now())
        if wait > 0:
            raise HttpError(429, "rate_limited", (("Retry-After", str(wait)),))
        data = App._read_body(request)
        return json_response(try_answers(_field(data, "receiver"), _field(data, "sender")).view())
