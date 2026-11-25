"""Errors of the case workflow. The code is safe to send to a browser."""

from __future__ import annotations


class ServiceError(Exception):
    """A request that cannot be done now. Carries a code, never user text."""

    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def not_found() -> ServiceError:
    """The case, scene, side or action does not exist."""
    return ServiceError("not_found", 404)


def wrong_step() -> ServiceError:
    """The case is not in the step this action needs."""
    return ServiceError("wrong_step", 409)


def stale_case() -> ServiceError:
    """The phone still shows a case that was reset."""
    return ServiceError("stale_case", 409)


def empty_answer() -> ServiceError:
    """The answer holds no text."""
    return ServiceError("empty_answer", 400)


def too_long() -> ServiceError:
    """The answer is longer than the limit."""
    return ServiceError("too_long", 400)
