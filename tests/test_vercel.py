"""The landing page on Vercel: the settings, and the one function behind the mini-demo."""

from __future__ import annotations

import http.client
import importlib.util
import json
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

import pytest

from bothsides import config
from bothsides.cases.tryout import try_answers
from bothsides.server.app import _PAGES
from bothsides.server.security import SECURITY_HEADERS

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "tests" / "shared" / "match_cases.json").read_text(encoding="utf-8"))
HOST = "both-sides.vercel.app"


def load_function() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vercel_compare", ROOT / "api" / "compare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def port() -> Iterator[int]:
    """The function behind a real socket, with fresh limits for every test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), load_function().handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def ask(port: int, body: Any, method: str = "POST", **headers: str) -> tuple[int, dict[str, Any], dict[str, str]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    sent = body if isinstance(body, bytes) else json.dumps(body).encode()
    base = {
        "Content-Type": "application/json",
        "Host": HOST,
        "Origin": f"https://{HOST}",
        "x-forwarded-host": HOST,
        "x-real-ip": "203.0.113.7",
    }
    connection.request(method, "/api/try", sent, {**base, **{key.replace("_", "-"): value for key, value in headers.items()}})
    reply = connection.getresponse()
    raw = reply.read()
    connection.close()
    return reply.status, json.loads(raw) if raw else {}, {key.lower(): value for key, value in reply.getheaders()}


# -- the function ----------------------------------------------------------------------------


def test_the_function_gives_the_verdict_of_the_app(port: int) -> None:
    pairs = [(case["receiver"], case["sender"]) for case in CASES["cases"]][: config.RATE_LIMIT_TRY - 2]
    assert len(pairs) > 10
    for receiver, sender in pairs:
        status, reply, _ = ask(port, {"receiver": receiver, "sender": sender})
        assert (status, reply) == (200, {"success": True, "data": try_answers(receiver, sender).view()})


def test_the_function_sends_the_headers_of_the_app(port: int) -> None:
    _, _, headers = ask(port, {"receiver": "друг вернул долг", "sender": "сестре на лечение"})
    for name, value in SECURITY_HEADERS:
        assert headers[name.lower()] == value


@pytest.mark.parametrize("origin", ["https://evil.example", "null", ""])
def test_other_sites_cannot_use_it(port: int, origin: str) -> None:
    status, reply, _ = ask(port, {"receiver": "брат", "sender": "брату"}, Origin=origin)
    assert (status, reply["error"]) == (403, "bad_origin")


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        (b"not json", 400, "bad_json"),
        (b"[]", 400, "bad_json"),
        (b"{}", 400, "bad_field"),
        (b'{"receiver": 1, "sender": "x"}', 400, "bad_field"),
        (b'{"receiver": " ", "sender": "x"}', 400, "empty_answer"),
        (json.dumps({"receiver": "а" * 301, "sender": "x"}).encode(), 400, "too_long"),
        (b"x" * (config.MAX_BODY_BYTES + 1), 413, "too_large"),
    ],
)
def test_bad_bodies_are_refused(port: int, body: bytes, status: int, code: str) -> None:
    answered, reply, _ = ask(port, body)
    assert (answered, reply["error"]) == (status, code)


def test_other_methods_are_refused(port: int) -> None:
    for method in ("GET", "PUT", "DELETE"):
        status, reply, _ = ask(port, b"", method)
        assert (status, reply["error"]) == (405, "bad_method")


def test_each_visitor_has_a_limit(port: int) -> None:
    body = {"receiver": "друг вернул долг", "sender": "сестре на лечение"}
    states = [ask(port, body)[0] for _ in range(config.RATE_LIMIT_TRY + 1)]
    assert states == [200] * config.RATE_LIMIT_TRY + [429]
    assert ask(port, body, x_real_ip="203.0.113.8")[0] == 200


def test_the_function_needs_no_package_and_no_key() -> None:
    code = (
        "import importlib.util, sys; "
        "spec = importlib.util.spec_from_file_location('compare', 'api/compare.py'); "
        "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "print(any(name.split('.')[0] == 'google' for name in sys.modules), 'bothsides.matching.gemini' in sys.modules)"
    )
    done = subprocess.run([sys.executable, "-S", "-B", "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert (done.returncode, done.stdout.split()[0]) == (0, "False"), done.stderr


# -- the settings -----------------------------------------------------------------------------


def all_headers(source: str) -> dict[str, str]:
    entry = next(item for item in SETTINGS["headers"] if item["source"] == source)
    return {item["key"]: item["value"] for item in entry["headers"]}


def test_pages_get_the_security_headers_of_the_app() -> None:
    sent = all_headers("/(.*)")
    expected = {name: value for name, value in SECURITY_HEADERS if name != "Cache-Control"}
    assert {name: sent[name] for name in expected} == expected
    assert sent["X-Robots-Tag"] == "noindex"


def test_every_address_of_the_app_is_served() -> None:
    rewrites = {item["source"]: item["destination"] for item in SETTINGS["rewrites"]}
    pages = next(source for source, target in rewrites.items() if target == "/app.html" and "start" in source)
    assert {f"/{name}" for name in pages.strip("/()").split("|")} == set(_PAGES)
    assert rewrites["/console/:id"] == "/app.html"
    assert rewrites["/api/try"] == "/api/compare"
    assert rewrites["/api/:path*"] == "/api/app?p=:path*"
    assert "redirects" not in SETTINGS


def test_the_functions() -> None:
    assert SETTINGS["outputDirectory"] == "web"
    assert set(SETTINGS["functions"]) == {"api/app.py", "api/compare.py"}


def test_only_what_is_needed_is_uploaded() -> None:
    lines = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    rules = [line for line in lines if line and not line.startswith("#")]
    assert rules[0] == "/*"
    assert {rule for rule in rules if rule.startswith("!")} == {"!/api", "!/bothsides", "!/web", "!/vercel.json", "!/requirements.txt"}


@pytest.mark.parametrize(
    ("raw", "target"),
    [
        ("/api/phone/receiver?p=phone/receiver", "/api/phone/receiver"),
        ("/api/app?p=phone/receiver", "/api/phone/receiver"),
        ("/api/app?p=cases/BS-2026-4111/release", "/api/cases/BS-2026-4111/release"),
        ("/api/stage", "/api/stage"),
    ],
)
def test_the_app_function_finds_the_address(raw: str, target: str) -> None:
    spec = importlib.util.spec_from_file_location("vercel_app", ROOT / "api" / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._target(raw) == target


def test_the_app_function_checks_the_model_within_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("vercel_app", ROOT / "api" / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks: list[str] = []

    class Setup:
        def confirm_model_now(self) -> None:
            checks.append("now")

    monkeypatch.setattr(module, "_SETUP", Setup())
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for path in ("/api/session", "/api/app?p=status", "/api/status", "/api/stage"):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", path, headers={"Host": HOST, "x-forwarded-host": HOST})
            assert connection.getresponse().status == 200
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
    assert checks == ["now", "now"]
