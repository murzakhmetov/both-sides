"""Reads the command line, the environment and an optional .env file."""

from __future__ import annotations

import argparse
import codecs
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

from . import config
from .server.auth import random_password

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class SettingsError(Exception):
    """A setting is wrong. The text is shown to the person at the terminal."""


@dataclass(frozen=True, slots=True)
class Settings:
    """How to run the server. The Gemini key is not kept here."""

    host: str
    port: int
    offline: bool
    staff_password: str
    password_is_random: bool
    allowed_hosts: frozenset[str]

    def __repr__(self) -> str:
        return f"Settings(host={self.host!r}, port={self.port}, offline={self.offline})"


def _parse_value(text: str) -> str:
    """Quoted text as it is; otherwise up to a comment, which needs a space before #."""
    if text[:1] in {"'", '"'}:
        closing = text.find(text[0], 1)
        if closing > 0:
            return text[1:closing]
    return re.split(r"(?:^|\s)#", text, maxsplit=1)[0].strip()


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#") or "=" not in text:
        return None
    name, value = text.split("=", 1)
    name = name.removeprefix("export ").strip()
    return (name, _parse_value(value.strip())) if name.isidentifier() else None


def _read_text(path: Path) -> str:
    """Notepad and Windows PowerShell may save UTF-16 with a byte order mark."""
    data = path.read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def load_env_file(path: Path, env: MutableMapping[str, str] | None = None) -> None:
    """Copy .env lines into the environment. Values that are already set win."""
    target = os.environ if env is None else env
    try:
        lines = _read_text(path).splitlines()
    except FileNotFoundError:
        return
    except UnicodeDecodeError:
        raise SettingsError(f"cannot read {path.name}: save the file as UTF-8") from None
    except OSError as error:
        raise SettingsError(f"cannot read {path.name}: {type(error).__name__}") from None
    for line in lines:
        pair = _parse_env_line(line)
        if pair and pair[1] and not target.get(pair[0]):
            target[pair[0]] = pair[1]


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("the port must be a number") from None
    if not 0 <= port <= 65_535:
        raise argparse.ArgumentTypeError("the port must be between 0 and 65535")
    return port


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py", description="Both sides: the bank asks both people about a stopped transfer."
    )
    parser.add_argument("--offline", action="store_true", help="use the offline matcher even with a key")
    parser.add_argument("--host", default=DEFAULT_HOST, help="0.0.0.0 opens the demo to the private network")
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT, help="default: 8000")
    return parser


def _staff_password(env: Mapping[str, str]) -> tuple[str, bool]:
    given = env.get("BOTHSIDES_STAFF_PASSWORD", "")
    if not given:
        return random_password(), True
    if not config.MIN_STAFF_PASSWORD_LENGTH <= len(given) <= config.MAX_PASSWORD_LENGTH:
        raise SettingsError(
            "BOTHSIDES_STAFF_PASSWORD needs at least "
            f"{config.MIN_STAFF_PASSWORD_LENGTH} and at most {config.MAX_PASSWORD_LENGTH} characters"
        )
    return given, False


def read_settings(arguments: Sequence[str], env: Mapping[str, str]) -> Settings:
    """Combine the command line and the environment."""
    parsed = _parser().parse_args(list(arguments))
    password, is_random = _staff_password(env)
    hosts = env.get("BOTHSIDES_ALLOWED_HOSTS", "")
    return Settings(
        host=parsed.host,
        port=parsed.port,
        offline=parsed.offline,
        staff_password=password,
        password_is_random=is_random,
        allowed_hosts=frozenset(name.strip().lower() for name in hosts.split(",") if name.strip()),
    )
