"""Starts the demo server and prints where to open it."""

from __future__ import annotations

import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Sequence

from .cases.service import CaseService
from .clock import SystemClock
from .matching.factory import MatcherSetup, MatcherStatus, build_matcher
from .server.app import App
from .server.auth import StaffAuth
from .server.http import Server, make_server, private_addresses
from .settings import Settings, SettingsError, load_env_file, read_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_EVERYWHERE = {"0.0.0.0", "::", ""}
_THIS_LAPTOP = {"localhost", "::1"}

_OFFLINE_REASONS = {
    "forced": "forced with --offline",
    "no_key": "GEMINI_API_KEY is not set",
    "no_package": "the package google-genai is not installed",
    "client_error": "the Gemini client could not be created",
}


def use_utf8_output() -> None:
    """Windows consoles may default to a code page without Kazakh letters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _matcher_line(status: MatcherStatus) -> str:
    if status.active == "gemini":
        return f"Matcher: Gemini ({status.model}), offline word list as fallback"
    return f"Matcher: offline word list ({_OFFLINE_REASONS.get(status.reason, status.reason)})"


def _phone_addresses(host: str, addresses: Sequence[str]) -> Sequence[str]:
    """Addresses that other devices on the private network can open."""
    if host in _EVERYWHERE:
        return addresses
    return () if host in _THIS_LAPTOP or host.startswith("127.") else (host,)


def banner(settings: Settings, port: int, status: MatcherStatus, addresses: Sequence[str]) -> str:
    """The text printed at start."""
    open_host = "127.0.0.1" if settings.host in _EVERYWHERE else settings.host
    local = f"http://{open_host}:{port}"
    lines = [
        "",
        "Both sides - prototype, invented people and amounts only",
        _matcher_line(status),
        "",
        f"  Landing page    {local}/",
        f"  Start page      {local}/start",
        f"  Receiver phone  {local}/receiver",
        f"  Sender phone    {local}/sender",
        f"  Demo (staff)    {local}/demo",
    ]
    phones = _phone_addresses(settings.host, addresses)
    lines += [f"  On real phones  http://{address}:{port}/receiver  and  /sender" for address in phones]
    if phones or settings.host in _EVERYWHERE:
        lines.append("  Open the demo to a private network only if you trust it.")
    if settings.password_is_random:
        lines += ["", f"  Staff password  {settings.staff_password}   (new at every start)"]
    else:
        lines += ["", "  Staff password  taken from BOTHSIDES_STAFF_PASSWORD"]
    return "\n".join([*lines, "", "Stop with Ctrl+C", ""])


def _first_number() -> int:
    """Another start, other case numbers: a phone that slept through a restart
    must not answer a new transfer with an old number."""
    return 1_000 + secrets.randbelow(8_000)


def build_app(settings: Settings, setup: MatcherSetup) -> App:
    """Wire everything together."""
    clock = SystemClock()
    return App(
        service=CaseService(clock=clock, matcher=setup.matcher, first_number=_first_number()),
        auth=StaffAuth(settings.staff_password, clock=clock),
        setup=setup,
        clock=clock,
        allowed_hosts=settings.allowed_hosts,
    )


def _open_server(app: App, settings: Settings) -> Server:
    try:
        return make_server(app, settings.host, settings.port)
    except OSError as error:
        raise SettingsError(
            f"cannot open {settings.host}:{settings.port} ({error.strerror or error}). "
            "Is another server running? Try --port 8001."
        ) from None


def run(arguments: Sequence[str]) -> int:
    """Run until Ctrl+C. Returns the exit code."""
    use_utf8_output()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        load_env_file(PROJECT_ROOT / ".env")
        settings = read_settings(arguments, os.environ)
        setup = build_matcher(settings.offline, os.environ)
        server = _open_server(build_app(settings, setup), settings)
    except SettingsError as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 2
    setup.confirm_model_in_background()
    print(banner(settings, server.server_address[1], setup.status(), private_addresses()), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()
    return 0
