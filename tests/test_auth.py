"""Staff password, sessions and lockout."""

from __future__ import annotations

from datetime import timedelta

import pytest

from bothsides import config
from bothsides.server.auth import (
    LoginFailed,
    LoginLocked,
    StaffAuth,
    hash_password,
    random_password,
    verify_password,
)

from .fakes import ManualClock
from .helpers import START
from .webclient import PASSWORD, TEST_ITERATIONS


def make_auth() -> tuple[StaffAuth, ManualClock]:
    clock = ManualClock(START)
    return StaffAuth(PASSWORD, clock=clock, iterations=TEST_ITERATIONS), clock


def fail(auth: StaffAuth, times: int, address: str = "10.0.0.5") -> None:
    for _ in range(times):
        with pytest.raises(LoginFailed):
            auth.login("wrong password", address)


def test_password_is_hashed_with_pbkdf2_and_a_salt() -> None:
    first, second = hash_password(PASSWORD, TEST_ITERATIONS), hash_password(PASSWORD, TEST_ITERATIONS)
    assert first.salt != second.salt and first.digest != second.digest
    assert PASSWORD.encode() not in first.digest
    assert verify_password(PASSWORD, first)
    assert not verify_password(PASSWORD + "x", first)
    assert config.PBKDF2_ITERATIONS >= 600_000


def test_password_is_not_kept_in_the_object() -> None:
    auth, _ = make_auth()
    assert PASSWORD not in repr(vars(auth))


def test_login_gives_a_valid_session() -> None:
    auth, _ = make_auth()
    token = auth.login(PASSWORD, "10.0.0.5")
    assert len(token) >= 32
    assert auth.is_valid(token)
    assert not auth.is_valid(token + "x")
    assert not auth.is_valid("")


def test_token_is_not_stored_in_clear() -> None:
    auth, _ = make_auth()
    token = auth.login(PASSWORD, "10.0.0.5")
    assert token not in repr(vars(auth))


def test_session_expires() -> None:
    auth, clock = make_auth()
    token = auth.login(PASSWORD, "10.0.0.5")
    clock.current += config.SESSION_LIFETIME - timedelta(seconds=1)
    assert auth.is_valid(token)
    clock.current += timedelta(seconds=2)
    assert not auth.is_valid(token)


def test_logout_ends_the_session() -> None:
    auth, _ = make_auth()
    token = auth.login(PASSWORD, "10.0.0.5")
    auth.logout(token)
    assert not auth.is_valid(token)
    auth.logout("unknown")


def test_lockout_after_failed_tries_even_with_the_right_password() -> None:
    auth, clock = make_auth()
    fail(auth, config.LOGIN_MAX_FAILURES)
    with pytest.raises(LoginLocked) as caught:
        auth.login(PASSWORD, "10.0.0.5")
    assert 0 < caught.value.seconds <= config.LOGIN_LOCKOUT.total_seconds()
    clock.current += config.LOGIN_LOCKOUT + timedelta(seconds=1)
    assert auth.login(PASSWORD, "10.0.0.5")


def test_parallel_tries_do_not_slip_past_the_lock() -> None:
    from concurrent.futures import ThreadPoolExecutor

    auth, _ = make_auth()

    def attempt(number: int) -> str:
        try:
            return "in" if auth.login("right" if number < 0 else f"wrong password {number}", "10.0.0.5") else ""
        except LoginLocked:
            return "locked"
        except LoginFailed:
            return "failed"

    with ThreadPoolExecutor(20) as pool:
        results = list(pool.map(attempt, range(20)))
    assert results.count("failed") == config.LOGIN_MAX_FAILURES
    assert results.count("locked") == 20 - config.LOGIN_MAX_FAILURES


def test_lockout_is_per_address() -> None:
    auth, _ = make_auth()
    fail(auth, config.LOGIN_MAX_FAILURES, "10.0.0.66")
    assert auth.login(PASSWORD, "10.0.0.5")


def test_old_failures_are_forgotten() -> None:
    auth, clock = make_auth()
    fail(auth, config.LOGIN_MAX_FAILURES - 1)
    clock.current += config.LOGIN_FAILURE_WINDOW + timedelta(seconds=1)
    fail(auth, config.LOGIN_MAX_FAILURES - 1)
    assert auth.login(PASSWORD, "10.0.0.5")


def test_success_clears_the_failures() -> None:
    auth, _ = make_auth()
    fail(auth, config.LOGIN_MAX_FAILURES - 1)
    auth.login(PASSWORD, "10.0.0.5")
    fail(auth, config.LOGIN_MAX_FAILURES - 1)
    assert auth.login(PASSWORD, "10.0.0.5")


def test_number_of_sessions_is_limited() -> None:
    auth, _ = make_auth()
    first = auth.login(PASSWORD, "10.0.0.5")
    for _ in range(config.MAX_STAFF_SESSIONS):
        last = auth.login(PASSWORD, "10.0.0.5")
    assert not auth.is_valid(first)
    assert auth.is_valid(last)


@pytest.mark.parametrize("password", ["", "short", "123456789"])
def test_short_password_is_refused(password: str) -> None:
    with pytest.raises(ValueError):
        StaffAuth(password, clock=ManualClock(START), iterations=TEST_ITERATIONS)


def test_random_password_is_long_and_readable() -> None:
    first, second = random_password(), random_password()
    assert first != second
    assert len(first) >= config.MIN_STAFF_PASSWORD_LENGTH
    assert not set(first) & set("0O1lI")
