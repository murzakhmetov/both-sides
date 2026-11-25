"""The landing page: the route /, the public comparison and the media files. No sockets here."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from bothsides import config
from bothsides.server.messages import Response

from .fakes import StubMatcher, gemini_result
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, SISTER_RECEIVER, SISTER_SENDER, as_json
from .webclient import WebClient, data, error, header, make_app

VIDEO = bytes(range(256)) * 4


@pytest.fixture
def web_root(tmp_path: Path) -> Path:
    media = tmp_path / "assets" / "landing"
    media.mkdir(parents=True)
    (tmp_path / "app.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (tmp_path / "index.html").write_text("<!doctype html><title>landing</title>", encoding="utf-8")
    (tmp_path / "assets" / "landing-abc123.js").write_text("export {}", encoding="utf-8")
    (media / "a-hero-16x9.mp4").write_bytes(VIDEO)
    (media / "a-hero-16x9.webp").write_bytes(b"picture")
    return tmp_path


@pytest.fixture
def web(web_root: Path) -> WebClient:
    return WebClient(make_app(web_root=web_root)[0])


def compare(web: WebClient, receiver: Any = SISTER_RECEIVER, sender: Any = SISTER_SENDER) -> Response:
    return web.post("/api/try", {"receiver": receiver, "sender": sender})


# -- the page ------------------------------------------------------------------------


def test_the_address_of_the_server_shows_the_landing_page(web: WebClient) -> None:
    response = web.get("/")
    assert response.status == 200
    assert b"<title>landing</title>" in response.body
    assert header(response, "content-type") == "text/html; charset=utf-8"
    assert header(response, "cache-control") == "no-store"
    assert "default-src 'none'" in header(response, "content-security-policy")


def test_without_a_landing_page_the_address_leads_to_the_app(web: WebClient, web_root: Path) -> None:
    (web_root / "index.html").unlink()
    response = web.get("/")
    assert (response.status, header(response, "location")) == (302, "/start")


def test_the_app_stays_where_it_was(web: WebClient) -> None:
    assert b"<title>app</title>" in web.get("/start").body
    assert b"<title>app</title>" in web.get("/nothing-here").body


# -- the public comparison -----------------------------------------------------------


def test_the_mother_story_goes_to_a_specialist(web: WebClient) -> None:
    answer = data(compare(web))
    assert answer["result"] == "specialist"
    assert "no_shared_reason" in answer["reasons"]


def test_the_rent_is_a_match(web: WebClient) -> None:
    assert data(compare(web, BROTHER_RECEIVER, BROTHER_SENDER)) == {"result": "match", "reasons": []}


def test_the_comparison_needs_no_login_and_sets_no_cookie(web: WebClient) -> None:
    response = compare(web)
    assert response.status == 200
    assert header(response, "set-cookie") == ""


def test_the_answers_do_not_come_back(web: WebClient) -> None:
    body = compare(web, "<b>друг вернул долг</b>", SISTER_SENDER).body.decode("utf-8")
    assert "друг" not in body and "сестре" not in body and "<b>" not in body


def test_nothing_is_stored_and_nothing_is_logged(web_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    app, _ = make_app(web_root=web_root)
    before = as_json([app.service.stage(), app.service.cases()])
    assert compare(WebClient(app), "попугай вернул клетку", "слону на бивни").status == 200
    assert as_json([app.service.stage(), app.service.cases()]) == before
    assert "попугай" not in caplog.text and "бивни" not in caplog.text


def test_the_language_model_is_never_asked(web_root: Path) -> None:
    class Counting(StubMatcher):
        calls = 0

        def compare(self, receiver: str, sender: str):  # type: ignore[no-untyped-def]
            Counting.calls += 1
            return super().compare(receiver, sender)

    web = WebClient(make_app(Counting(gemini_result(0.99)), web_root)[0])
    assert data(compare(web))["result"] == "specialist"
    assert Counting.calls == 0


@pytest.mark.parametrize(
    ("receiver", "sender", "code"),
    [
        ("", SISTER_SENDER, "empty_answer"),
        (SISTER_RECEIVER, "   ", "empty_answer"),
        ("а" * (config.MAX_ANSWER_LENGTH + 1), SISTER_SENDER, "too_long"),
        (SISTER_RECEIVER, "ﷺ" * 100, "too_long"),
        (None, SISTER_SENDER, "bad_field"),
        (SISTER_RECEIVER, 5, "bad_field"),
        (["а"], SISTER_SENDER, "bad_field"),
    ],
)
def test_bad_answers_are_refused(web: WebClient, receiver: Any, sender: Any, code: str) -> None:
    response = compare(web, receiver, sender)
    assert (response.status, error(response)) == (400, code)


def test_other_sites_and_other_forms_are_refused(web: WebClient) -> None:
    body = {"receiver": SISTER_RECEIVER, "sender": SISTER_SENDER}
    assert web.post("/api/try", body, origin="http://evil.example").status == 403
    assert web.post("/api/try", body, **{"content-type": "text/plain"}).status == 415
    assert web.post("/api/try", {**body, "more": "x" * config.MAX_BODY_BYTES}).status == 413
    assert web.get("/api/try").status == 405


def test_the_comparison_has_its_own_small_limit(web: WebClient) -> None:
    statuses = [compare(web).status for _ in range(config.RATE_LIMIT_TRY + 1)]
    assert set(statuses[:-1]) == {200}
    assert statuses[-1] == 429
    assert int(header(compare(web), "retry-after")) > 0
    # The phones of the demo go on working on the same laptop.
    assert web.post("/api/phone/receiver/deny", {"case_id": "x"}).status == 409


def test_a_busy_demo_does_not_stop_the_comparison(web: WebClient) -> None:
    for _ in range(config.RATE_LIMIT_WRITES + 1):
        last = web.post("/api/phone/receiver/deny", {"case_id": "x"})
    assert last.status == 429
    assert compare(web).status == 200


# -- media files ---------------------------------------------------------------------

CLIP = "/assets/landing/a-hero-16x9.mp4"


@pytest.mark.parametrize(
    ("wanted", "first", "last"),
    [
        ("bytes=0-1", 0, 1),
        ("bytes=100-199", 100, 199),
        ("bytes=1000-", 1000, 1023),
        ("bytes=-24", 1000, 1023),
        ("bytes=-5000", 0, 1023),
        ("bytes=1000-99999", 1000, 1023),
    ],
)
def test_a_player_may_ask_for_a_part(web: WebClient, wanted: str, first: int, last: int) -> None:
    response = web.get(CLIP, range=wanted)
    assert response.status == 206
    assert header(response, "content-range") == f"bytes {first}-{last}/{len(VIDEO)}"
    assert response.body == VIDEO[first : last + 1]
    assert header(response, "content-type") == "video/mp4"


@pytest.mark.parametrize("wanted", ["bytes=1024-", "bytes=5000-6000", "bytes=-0"])
def test_a_part_behind_the_end_is_refused(web: WebClient, wanted: str) -> None:
    response = web.get(CLIP, range=wanted)
    assert response.status == 416
    assert header(response, "content-range") == f"bytes */{len(VIDEO)}"
    assert response.body == b""


@pytest.mark.parametrize(
    "wanted", ["", "bytes=", "bytes=-", "bytes=9-2", "bytes=0-1,5-6", "items=0-1", "bytes=a-b", "bytes=0-" + "9" * 400, "bytes=١-٢"]
)
def test_a_strange_wish_gets_the_whole_file(web: WebClient, wanted: str) -> None:
    response = web.get(CLIP, range=wanted)
    assert response.status == 200
    assert response.body == VIDEO
    assert header(response, "accept-ranges") == "bytes"


def test_files_that_keep_their_name_are_not_kept_for_a_year(web: WebClient) -> None:
    assert "immutable" in header(web.get("/assets/landing-abc123.js"), "cache-control")
    for path in (CLIP, "/assets/landing/a-hero-16x9.webp"):
        assert header(web.get(path), "cache-control") == "public, max-age=3600"


def test_pages_have_no_parts(web: WebClient) -> None:
    response = web.get("/", range="bytes=0-3")
    assert response.status == 200
    assert response.body.endswith(b"</title>")
