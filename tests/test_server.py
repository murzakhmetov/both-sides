"""The web app: pages, API, protection. No sockets here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bothsides import config
from bothsides.matching.types import Tri

from .fakes import StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER
from .webclient import HOST, ORIGIN, PASSWORD, WebClient, data, error, header, make_app, payload

STAFF_GETS = ["/api/stage", "/api/cases", "/api/cases/BS-2026-0001", "/api/scenes", "/api/matcher"]
STAFF_POSTS = [
    "/api/reset",
    "/api/scenes/brother/start",
    "/api/cases/BS-2026-0001/release",
    "/api/cases/BS-2026-0001/return",
]
STAFF_PAGES = ["/stage", "/console", "/demo", "/console/BS-2026-0001"]
PUBLIC_PAGES = ["/start", "/receiver", "/sender", "/login"]


@pytest.fixture
def web_root(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "app.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (tmp_path / "assets" / "app-abc123.js").write_text("export {}", encoding="utf-8")
    (tmp_path / "assets" / "app-abc123.css").write_text("body{}", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("secret", encoding="utf-8")
    return tmp_path


def client(matcher: object = None, web_root: Path | None = None) -> WebClient:
    app, _ = make_app(matcher, web_root)  # type: ignore[arg-type]
    return WebClient(app)


def staff(matcher: object = None, web_root: Path | None = None) -> WebClient:
    signed_in = client(matcher, web_root)
    assert signed_in.login().status == 200
    return signed_in


def case_id(web: WebClient) -> str:
    return data(web.get("/api/phone/receiver"))["case_id"]


# -- pages ---------------------------------------------------------------------


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages(path: str, web_root: Path) -> None:
    response = client(web_root=web_root).get(path)
    assert response.status == 200
    assert header(response, "content-type") == "text/html; charset=utf-8"
    assert header(response, "cache-control") == "no-store"


@pytest.mark.parametrize("path", STAFF_PAGES)
def test_staff_pages_ask_for_the_password(path: str, web_root: Path) -> None:
    response = client(web_root=web_root).get(path)
    assert response.status == 303
    assert header(response, "location") == f"/login?next={path}"
    assert staff(web_root=web_root).get(path).status == 200


def test_root_leads_to_the_start_page(web_root: Path) -> None:
    response = client(web_root=web_root).get("/")
    assert response.status == 302
    assert header(response, "location") == "/start"


def test_assets_have_types_and_long_caching(web_root: Path) -> None:
    web = client(web_root=web_root)
    script = web.get("/assets/app-abc123.js")
    assert header(script, "content-type") == "text/javascript; charset=utf-8"
    assert "immutable" in header(script, "cache-control")
    assert header(web.get("/assets/app-abc123.css"), "content-type") == "text/css; charset=utf-8"


@pytest.mark.parametrize(
    "path",
    [
        "/assets/../../secret.txt",
        "/assets/..%2f..%2fsecret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/assets/..\\..\\secret.txt",
        "/assets//etc/passwd",
        "/assets/C:/Windows/win.ini",
        "/assets/\x00.js",
        "/assets/",
        "/assets/missing.js",
        "/app.html",
        "/unknown",
    ],
)
def test_nothing_outside_the_build_is_served(path: str, web_root: Path) -> None:
    response = client(web_root=web_root).get(path)
    assert response.status == 404
    assert b"secret" not in response.body


def test_people_get_a_page_for_a_wrong_address_and_programs_get_json(web_root: Path) -> None:
    web = client(web_root=web_root)
    assert header(web.get("/nothing-here"), "content-type").startswith("text/html")
    assert error(web.get("/api/nothing-here")) == "not_found"
    for path in ("/receiver/", "/console/", "/demo//"):
        response = web.get(path)
        assert (response.status, header(response, "location")) == (302, path.rstrip("/"))


def test_missing_build_is_explained(tmp_path: Path) -> None:
    response = client(web_root=tmp_path / "nowhere").get("/start")
    assert response.status == 503
    assert b"npm run build" in response.body


# -- security headers ------------------------------------------------------------


@pytest.mark.parametrize("path", ["/start", "/api/status", "/api/phone/receiver", "/unknown", "/api/stage"])
def test_every_response_has_security_headers(path: str, web_root: Path) -> None:
    response = client(web_root=web_root).get(path)
    policy = header(response, "content-security-policy")
    assert "default-src 'none'" in policy
    assert "script-src 'self'" in policy
    assert "style-src 'self'" in policy
    assert "frame-ancestors 'self'" in policy
    assert "frame-src 'self'" in policy
    assert "unsafe" not in policy
    assert header(response, "x-content-type-options") == "nosniff"
    assert header(response, "x-frame-options") == "SAMEORIGIN"
    assert header(response, "referrer-policy") == "no-referrer"


# -- origin, host, body ------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    ["", "null", "http://evil.example", "http://127.0.0.1:9999", "http://127.0.0.1.evil.example:8000", "ftp://127.0.0.1:8000", "http://localhost:8000"],
)
def test_post_from_another_origin_is_refused(origin: str) -> None:
    web = client()
    response = web.post("/api/phone/receiver/answer", {"case_id": case_id(web), "text": "брат аренда"}, origin=origin)
    assert response.status == 403
    assert error(response) == "bad_origin"


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "8.8.8.8:8000", "", "127.0.0.1.evil.example"])
def test_unknown_host_is_refused(host: str) -> None:
    response = client().get("/api/status", host=host)
    assert response.status == 421
    assert error(response) == "bad_host"


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1", "[::1]:8000", "192.168.1.20:8000", "10.0.0.7:8000", "172.20.1.1"])
def test_private_hosts_are_allowed(host: str) -> None:
    assert client().get("/api/status", host=host).status == 200


def test_same_origin_on_the_private_network_is_allowed() -> None:
    web = client()
    response = web.post(
        "/api/phone/receiver/answer",
        {"case_id": case_id(web), "text": BROTHER_RECEIVER},
        host="192.168.1.20:8000",
        origin="http://192.168.1.20:8000",
    )
    assert response.status == 200


@pytest.mark.parametrize(
    ("body", "content_type", "status", "code"),
    [
        (b"{}", "text/plain", 415, "bad_content_type"),
        (b"{}", "application/x-www-form-urlencoded", 415, "bad_content_type"),
        (b"not json", "application/json", 400, "bad_json"),
        (b"[]", "application/json", 400, "bad_json"),
        (b"\xff\xfe", "application/json", 400, "bad_json"),
        (b'{"case_id": 5, "text": "x"}', "application/json", 400, "bad_field"),
        (b'{"text": "x"}', "application/json", 400, "bad_field"),
        (b'{"case_id": "x"}', "application/json", 400, "bad_field"),
    ],
)
def test_bad_bodies(body: bytes, content_type: str, status: int, code: str) -> None:
    response = client().request(
        "POST", "/api/phone/receiver/answer", body, {"origin": ORIGIN, "content-type": content_type}
    )
    assert (response.status, error(response)) == (status, code)


def test_large_body_is_refused() -> None:
    body = json.dumps({"case_id": "x", "text": "y" * config.MAX_BODY_BYTES}).encode()
    response = client().request(
        "POST", "/api/phone/receiver/answer", body, {"origin": ORIGIN, "content-type": "application/json"}
    )
    assert response.status == 413


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS", "TRACE"])
def test_other_methods_are_refused(method: str) -> None:
    assert client().request(method, "/api/status").status == 405


def test_wrong_method_on_a_known_path() -> None:
    web = client()
    assert web.get("/api/login").status == 405
    assert web.post("/api/status").status == 405


def test_unknown_api_path() -> None:
    response = client().get("/api/nothing")
    assert (response.status, error(response)) == (404, "not_found")


def test_internal_errors_are_generic(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    web = client()

    def broken(*_: object) -> None:
        raise RuntimeError("secret detail брат аренда")

    monkeypatch.setattr(web.app.service, "phone", broken)
    response = web.get("/api/phone/receiver")
    assert (response.status, error(response)) == (500, "server_error")
    assert "secret detail" not in response.body.decode()
    assert "secret detail" not in caplog.text


# -- status and phones -------------------------------------------------------------


def test_status_names_the_active_matcher() -> None:
    status = data(client().get("/api/status"))
    assert status["matcher"] == {"active": "offline", "reason": "forced", "model": "", "model_state": ""}


def test_phone_flow_over_the_api() -> None:
    web = client()
    number = case_id(web)
    view = data(web.post("/api/phone/receiver/answer", {"case_id": number, "text": BROTHER_RECEIVER}))
    assert view["status"] == "waiting"
    view = data(web.post("/api/phone/sender/answer", {"case_id": number, "text": BROTHER_SENDER}))
    assert view["status"] == "credited"


def test_phone_errors_have_codes() -> None:
    web = client()
    number = case_id(web)
    late = web.post("/api/phone/sender/answer", {"case_id": number, "text": BROTHER_SENDER})
    assert (late.status, error(late)) == (409, "wrong_step")
    stale = web.post("/api/phone/receiver/answer", {"case_id": "BS-2026-9999", "text": BROTHER_RECEIVER})
    assert (stale.status, error(stale)) == (409, "stale_case")
    long = web.post("/api/phone/receiver/answer", {"case_id": number, "text": "x" * 301})
    assert (long.status, error(long)) == (400, "too_long")
    assert web.get("/api/phone/nobody").status == 404


def test_denial_over_the_api() -> None:
    web = staff()
    web.post("/api/scenes/stranger/start")
    number = case_id(web)
    assert data(web.post("/api/phone/receiver/deny", {"case_id": number}))["status"] == "question"
    assert data(web.post("/api/phone/receiver/deny", {"case_id": number}))["status"] == "return_offer"
    assert data(web.post("/api/phone/receiver/accept-return", {"case_id": number}))["status"] == "returned"


def test_sender_has_no_denial_button() -> None:
    web = client()
    assert web.post("/api/phone/sender/deny", {"case_id": case_id(web)}).status == 404
    assert web.post("/api/phone/sender/accept-return", {"case_id": case_id(web)}).status == 404


def test_hold_and_objection_over_the_api() -> None:
    web = staff(StubMatcher(gemini_result(0.02, Tri.FALSE, Tri.FALSE)))
    web.post("/api/scenes/sister/start")
    number = case_id(web)
    web.post("/api/phone/receiver/answer", {"case_id": number, "text": SISTER_RECEIVER})
    web.post("/api/phone/sender/answer", {"case_id": number, "text": SISTER_SENDER})
    view = data(web.post("/api/phone/sender/objection", {"case_id": number}))
    assert (view["status"], view["objection_sent"]) == ("held", True)
    file = data(web.get(f"/api/cases/{number}"))
    assert file["objections"][0]["side"] == "sender"
    assert data(web.post(f"/api/cases/{number}/return"))["state"] == "returned"


def test_user_text_is_escaped_for_the_browser() -> None:
    web = staff()
    number = case_id(web)
    attack = "</script><script>alert(1)</script> брат аренда"
    web.post("/api/phone/receiver/answer", {"case_id": number, "text": attack})
    body = web.get(f"/api/cases/{number}").body.decode()
    assert "<script" not in body and "</script" not in body
    assert json.loads(body)["data"]["receiver_answer"]["text"] == attack


# -- staff ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", STAFF_GETS)
def test_staff_api_needs_a_session(path: str) -> None:
    response = client().get(path)
    assert (response.status, error(response)) == (401, "login_required")
    assert staff().get(path).status in {200, 404}


@pytest.mark.parametrize("path", STAFF_POSTS)
def test_staff_actions_need_a_session(path: str) -> None:
    response = client().post(path)
    assert (response.status, error(response)) == (401, "login_required")


def test_forged_cookie_is_refused() -> None:
    web = client()
    web.cookie = "bs_staff=forged"
    assert web.get("/api/stage").status == 401


def test_login_sets_a_protected_cookie() -> None:
    response = client().login()
    cookie = header(response, "set-cookie")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie
    assert "Max-Age=28800" in cookie
    assert PASSWORD not in response.body.decode() and PASSWORD not in cookie


def test_wrong_password_and_lockout() -> None:
    web = client()
    for _ in range(config.LOGIN_MAX_FAILURES):
        response = web.login("wrong password")
        assert (response.status, error(response)) == (401, "wrong_password")
    locked = web.login()
    assert (locked.status, error(locked)) == (429, "locked")
    assert int(header(locked, "retry-after")) > 0


def test_overlong_password_is_refused_without_hashing() -> None:
    response = client().login("x" * (config.MAX_PASSWORD_LENGTH + 1))
    assert (response.status, error(response)) == (401, "wrong_password")


def test_logout_clears_the_cookie() -> None:
    web = staff()
    assert data(web.get("/api/session"))["staff"] is True
    response = web.post("/api/logout")
    assert "Max-Age=0" in header(response, "set-cookie")
    assert data(web.get("/api/session"))["staff"] is False


def test_scenes_list_has_the_scripts_for_staff_only() -> None:
    web = staff()
    reply = data(web.get("/api/scenes"))
    assert reply["case_id"] == case_id(web)
    scenes = reply["scenes"]
    assert [scene["id"] for scene in scenes] == ["brother", "sister", "stranger"]
    assert scenes[0]["receiver_script"] == BROTHER_RECEIVER
    assert scenes[0]["sender_script"] == BROTHER_SENDER


def test_unknown_scene_and_case() -> None:
    web = staff()
    assert web.post("/api/scenes/nothing/start").status == 404
    assert web.get("/api/cases/BS-0000-0000").status == 404
    assert web.post("/api/cases/BS-0000-0000/release").status == 404


# -- rate limits ------------------------------------------------------------------------


def test_write_limit_per_address() -> None:
    app, clock = make_app()
    web = WebClient(app)
    statuses = [web.post("/api/phone/receiver/deny", {"case_id": "x"}).status for _ in range(config.RATE_LIMIT_WRITES + 1)]
    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]
    assert WebClient(app, address="10.0.0.9").post("/api/phone/receiver/deny", {"case_id": "x"}).status == 409
    clock.advance(seconds=61)
    assert web.post("/api/phone/receiver/deny", {"case_id": "x"}).status == 409


def test_reads_allow_four_polling_screens() -> None:
    # Two phones, the stage and the demo page at one request per second each, and more.
    assert config.RATE_LIMIT_READS >= 4 * 60 * 2


def test_read_limit_exists() -> None:
    web = client()
    for _ in range(config.RATE_LIMIT_READS):
        assert web.get("/api/status").status == 200
    response = web.get("/api/status")
    assert (response.status, error(response)) == (429, "rate_limited")


def test_head_is_answered_like_get(web_root: Path) -> None:
    web = client(web_root=web_root)
    assert web.request("HEAD", "/start").status == 200
    assert web.request("HEAD", "/api/stage").status == 401
    assert web.request("HEAD", "/stage").status == 303


# -- found by a security review ------------------------------------------------------------


@pytest.mark.parametrize(
    "neighbour",
    ['prefs={"theme":"dark"}', "version=1.2.3", "path=/x", "domain=a", "name=John Smith", 'q=a"b', "flag", "city=Алматы", "a[0]=1"],
)
def test_cookies_of_other_local_apps_do_not_break_the_session(neighbour: str) -> None:
    web = staff()
    web.cookie = f"{neighbour}; {web.cookie}; other=1"
    assert data(web.get("/api/session"))["staff"] is True


def test_long_cookie_header_is_cheap() -> None:
    import time

    started = time.perf_counter()
    web = client()
    web.cookie = "a=" * 30_000 + '"'
    assert data(web.get("/api/session"))["staff"] is False
    assert time.perf_counter() - started < 1.0


def test_refused_requests_of_other_sites_do_not_spend_the_limit() -> None:
    web = client()
    for _ in range(config.RATE_LIMIT_LOGIN + 5):
        assert web.post("/api/login", {"password": "x"}, origin="http://evil.example").status == 403
    assert web.login().status == 200
    for _ in range(config.RATE_LIMIT_READS + 5):
        assert web.request("GET", "/api/status", headers={"sec-fetch-site": "cross-site"}).status == 403
    assert web.get("/api/status").status == 200


def test_pages_loaded_by_another_site_do_not_stop_the_phones(web_root: Path) -> None:
    web = client(web_root=web_root)
    statuses = [
        web.request("GET", "/start", headers={"sec-fetch-site": "cross-site"}).status
        for _ in range(config.RATE_LIMIT_PAGES + 5)
    ]
    assert (statuses[0], statuses[-1]) == (200, 429)
    assert web.get("/api/phone/receiver").status == 200


def test_retry_after_is_the_real_waiting_time() -> None:
    app, clock = make_app()
    web = WebClient(app)
    for _ in range(config.RATE_LIMIT_LOGIN):
        web.post("/api/login", {"password": "wrong password"})
    clock.advance(seconds=15)
    assert int(header(web.login(), "retry-after")) == 45


def test_broken_text_is_a_wrong_password() -> None:
    web = client()
    body = b'{"password": "\\ud800"}'
    statuses = [
        web.request("POST", "/api/login", body, {"origin": ORIGIN, "content-type": "application/json"}).status
        for _ in range(config.LOGIN_MAX_FAILURES + 1)
    ]
    assert statuses == [401] * config.LOGIN_MAX_FAILURES + [429]


@pytest.mark.parametrize("path", ["/assets/" + "x" * 32_700 + ".js", "/assets/" + "x/" * 16_000 + "y.json"])
def test_very_long_paths_are_not_looked_up(path: str, web_root: Path) -> None:
    assert client(web_root=web_root).get(path).status == 404


def test_characters_that_expand_count_by_their_real_length() -> None:
    web = client()
    response = web.post("/api/phone/receiver/answer", {"case_id": case_id(web), "text": "\ufdfa" * 300})
    assert (response.status, error(response)) == (400, "too_long")


def test_payload_shape() -> None:
    assert set(payload(client().get("/api/status"))) == {"success", "data"}
    assert set(payload(client().get("/api/nothing"))) == {"success", "error"}


def test_host_constant_is_local() -> None:
    assert HOST.startswith("127.0.0.1")
