"""Staff login: PBKDF2 password, random session tokens, lockout, expiry."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime

from .. import config
from ..clock import Clock

_SALT_BYTES = 16
_READABLE = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class LoginFailed(Exception):
    """The password is wrong."""


class LoginLocked(Exception):
    """Too many failed tries from this address."""

    def __init__(self, seconds: int) -> None:
        super().__init__("locked")
        self.seconds = seconds


@dataclass(frozen=True, slots=True)
class PasswordHash:
    """A salted PBKDF2 digest."""

    salt: bytes
    digest: bytes
    iterations: int


def _digest(password: str, salt: bytes, iterations: int) -> bytes:
    # "surrogatepass": broken text from a client is a wrong password, not an error.
    data = password.encode("utf-8", "surrogatepass")
    return hashlib.pbkdf2_hmac("sha256", data, salt, iterations)


def hash_password(password: str, iterations: int) -> PasswordHash:
    """Hash a password with a fresh salt."""
    salt = secrets.token_bytes(_SALT_BYTES)
    return PasswordHash(salt, _digest(password, salt, iterations), iterations)


def verify_password(password: str, stored: PasswordHash) -> bool:
    """Compare in constant time."""
    return hmac.compare_digest(_digest(password, stored.salt, stored.iterations), stored.digest)


def random_password(groups: int = 3, size: int = 4) -> str:
    """A random password without look-alike characters, like abcd-efgh-jkmn."""
    parts = ("".join(secrets.choice(_READABLE) for _ in range(size)) for _ in range(groups))
    return "-".join(parts)


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest()


class StaffAuth:
    """Keeps only the password hash and token hashes in memory."""

    def __init__(self, password: str, clock: Clock, iterations: int = config.PBKDF2_ITERATIONS) -> None:
        if len(password) < config.MIN_STAFF_PASSWORD_LENGTH:
            raise ValueError(f"the staff password needs at least {config.MIN_STAFF_PASSWORD_LENGTH} characters")
        self._hash = hash_password(password, iterations)
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, datetime] = {}
        self._failures: dict[str, tuple[datetime, ...]] = {}
        self._locked_until: dict[str, datetime] = {}

    def login(self, password: str, address: str) -> str:
        """Return a new session token or raise LoginFailed / LoginLocked.

        Every try is counted before the slow hash, so that tries in parallel
        cannot slip past the lock. A right password clears the count.
        """
        with self._lock:
            self._check_lock(address)
            self._count_try(address)
        if len(password) > config.MAX_PASSWORD_LENGTH or not verify_password(password, self._hash):
            raise LoginFailed()
        with self._lock:
            self._failures = {key: value for key, value in self._failures.items() if key != address}
            self._locked_until = {key: value for key, value in self._locked_until.items() if key != address}
            return self._new_session()

    def is_valid(self, token: str) -> bool:
        """True for a known session that has not expired."""
        if not token:
            return False
        with self._lock:
            expires = self._sessions.get(_token_key(token))
        return expires is not None and self._clock.now() < expires

    def logout(self, token: str) -> None:
        """Forget this session."""
        key = _token_key(token)
        with self._lock:
            self._sessions = {name: value for name, value in self._sessions.items() if name != key}

    def _check_lock(self, address: str) -> None:
        now = self._clock.now()
        until = self._locked_until.get(address)
        if until is not None and now < until:
            raise LoginLocked(max(1, math.ceil((until - now).total_seconds())))

    def _count_try(self, address: str) -> None:
        now = self._clock.now()
        recent = tuple(
            at for at in self._failures.get(address, ()) if now - at < config.LOGIN_FAILURE_WINDOW
        )
        failures = (*recent, now)
        if len(failures) < config.LOGIN_MAX_FAILURES:
            self._failures = {**self._failures, address: failures}
            return
        self._failures = {key: value for key, value in self._failures.items() if key != address}
        self._locked_until = {**self._locked_until, address: now + config.LOGIN_LOCKOUT}

    def _new_session(self) -> str:
        now = self._clock.now()
        token = secrets.token_urlsafe(32)
        alive = {key: expires for key, expires in self._sessions.items() if now < expires}
        newest = dict(sorted(alive.items(), key=lambda item: item[1])[-(config.MAX_STAFF_SESSIONS - 1) :])
        self._sessions = {**newest, _token_key(token): now + config.SESSION_LIFETIME}
        return token
