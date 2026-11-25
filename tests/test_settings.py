"""Command line, environment, .env file and the start banner."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from bothsides.main import banner, build_app, run
from bothsides.matching.factory import MatcherStatus, build_matcher
from bothsides.settings import Settings, SettingsError, load_env_file, read_settings

from .helpers import start_output

ROOT = Path(__file__).resolve().parents[1]
KEY = "unit-test-key-value"


def test_defaults_are_local() -> None:
    settings = read_settings([], {})
    assert (settings.host, settings.port, settings.offline) == ("127.0.0.1", 8000, False)
    assert settings.password_is_random


def test_arguments() -> None:
    settings = read_settings(["--offline", "--host", "0.0.0.0", "--port", "8123"], {})
    assert (settings.host, settings.port, settings.offline) == ("0.0.0.0", 8123, True)


@pytest.mark.parametrize("port", ["abc", "-1", "70000"])
def test_bad_port(port: str) -> None:
    with pytest.raises(SystemExit):
        read_settings(["--port", port], {})


def test_password_from_the_environment() -> None:
    settings = read_settings([], {"BOTHSIDES_STAFF_PASSWORD": "long-enough-1"})
    assert settings.staff_password == "long-enough-1"
    assert not settings.password_is_random


@pytest.mark.parametrize("password", ["short", "123456789", "x" * 201])
def test_bad_password_is_refused(password: str) -> None:
    with pytest.raises(SettingsError):
        read_settings([], {"BOTHSIDES_STAFF_PASSWORD": password})


def test_random_passwords_differ() -> None:
    assert read_settings([], {}).staff_password != read_settings([], {}).staff_password


def test_settings_repr_hides_the_password() -> None:
    settings = read_settings([], {"BOTHSIDES_STAFF_PASSWORD": "long-enough-1"})
    assert "long-enough-1" not in repr(settings)


def test_allowed_hosts() -> None:
    assert read_settings([], {"BOTHSIDES_ALLOWED_HOSTS": "Demo.local, laptop "}).allowed_hosts == {"demo.local", "laptop"}


def test_env_file(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text(
        "# comment\nGEMINI_API_KEY=from-file\nexport GEMINI_MODEL='gemini-x-flash'\nBROKEN LINE\nEMPTY=\nSET=file\n1BAD=x\n",
        encoding="utf-8",
    )
    env = {"SET": "already"}
    load_env_file(file, env)
    assert env == {"SET": "already", "GEMINI_API_KEY": "from-file", "GEMINI_MODEL": "gemini-x-flash"}


def test_env_file_with_a_byte_order_mark(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_bytes(b"\xef\xbb\xbfGEMINI_API_KEY=abc\r\n")
    env: dict[str, str] = {}
    load_env_file(file, env)
    assert env == {"GEMINI_API_KEY": "abc"}


def test_missing_env_file_is_fine(tmp_path: Path) -> None:
    load_env_file(tmp_path / "none", {})


def test_unreadable_env_file_is_explained(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_bytes(b"\xff\xfe\x00GEMINI")
    with pytest.raises(SettingsError) as caught:
        load_env_file(file, {})
    assert "GEMINI" not in str(caught.value)


def make_settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "host": "127.0.0.1",
        "port": 8000,
        "offline": True,
        "staff_password": "abcd-efgh-jkmn",
        "password_is_random": True,
        "allowed_hosts": frozenset(),
        **changes,
    }
    return Settings(**values)  # type: ignore[arg-type]


def test_banner_shows_a_random_password_only() -> None:
    status = MatcherStatus(active="offline", reason="no_key")
    assert "abcd-efgh-jkmn" in banner(make_settings(), 8000, status, ())
    given = banner(make_settings(password_is_random=False), 8000, status, ())
    assert "abcd-efgh-jkmn" not in given
    assert "GEMINI_API_KEY is not set" in given


def test_banner_lists_private_addresses_only_when_open() -> None:
    status = MatcherStatus(active="gemini", model="gemini-3.8-flash")
    assert "192.168.1.20" in banner(make_settings(host="0.0.0.0"), 8000, status, ("192.168.1.20",))
    assert "192.168.1.20" not in banner(make_settings(), 8000, status, ("192.168.1.20",))


def test_app_is_wired() -> None:
    app = build_app(make_settings(), build_matcher(offline=True, env={}))
    assert app.service.phone("receiver")["status"] == "question"


def test_taken_port_is_explained(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOTHSIDES_STAFF_PASSWORD", raising=False)
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]
        assert run(["--offline", "--port", str(port)]) == 2
    assert "Cannot start" in capsys.readouterr().err


def test_short_password_stops_the_start(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOTHSIDES_STAFF_PASSWORD", "short")
    assert run(["--offline"]) == 2
    message = capsys.readouterr().err
    assert "at least 10" in message and "short" not in message.replace("short password", "")


def test_start_command_in_a_real_process(tmp_path: Path) -> None:
    """Starts run.py from another folder, without any installed package, on a cp1251 console."""
    env = {**os.environ, "PYTHONIOENCODING": "cp1251", "GEMINI_API_KEY": ""}
    env.pop("BOTHSIDES_STAFF_PASSWORD", None)
    seen, errors = start_output(["--offline", "--port", "0"], env, tmp_path)
    assert b"Staff password" in seen, errors.decode(errors="replace")
    assert b"offline word list" in seen


def test_key_is_never_in_the_source() -> None:
    import re

    pattern = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
    for folder in ("bothsides", "tests", "evaluation", "tools"):
        for file in (ROOT / folder).rglob("*.py"):
            assert not pattern.search(file.read_text(encoding="utf-8")), file
