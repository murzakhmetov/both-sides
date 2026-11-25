"""Found by a robustness review: odd characters, clock steps, a late network, odd .env files."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bothsides.cases.service import clean_answer
from bothsides.clock import SystemClock
from bothsides.config import BANK_TIMEZONE
from bothsides.main import banner
from bothsides.matching.factory import MatcherSetup, MatcherStatus, build_matcher
from bothsides.settings import SettingsError, load_env_file
from bothsides.textnorm import one_line

from .fakes import FakeGeminiClient, gemini_reply
from .helpers import BROTHER_RECEIVER, BROTHER_SENDER, active_id, make_service
from .test_settings import make_settings

START = datetime(2026, 11, 26, 12, tzinfo=BANK_TIMEZONE)
#: Soft hyphen, zero-width signs, direction mark; joiner, variation selector, stress mark.
INVISIBLE = ["\u00ad", "\u200b", "\u200c", "\u2060", "\u200f", "\u034f", "\ufe0f", "\u0301"]


# -- invisible characters -------------------------------------------------------------


@pytest.mark.parametrize("char", INVISIBLE)
def test_invisible_characters_inside_a_word_are_dropped(char: str) -> None:
    assert clean_answer(f"я не зн{char}аю этого чело{char}века") == "я не знаю этого человека"
    assert one_line(f"брат{char}у\tза\nаренду\x00квартиры") == "брату за аренду квартиры"


@pytest.mark.parametrize("char", INVISIBLE)
@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("я не зн{0}аю этого чело{0}века", "denial_in_text"),
        ("бұл адамды таны{0}маймын", "denial_in_text"),
        ("мне ска{0}зали так ска{0}зать", "coached_in_text"),
    ],
)
def test_denials_with_invisible_characters_go_to_a_person(char: str, text: str, reason: str) -> None:
    service, _ = make_service()
    service.answer("receiver", active_id(service), text.format(char))
    file = service.case_file(active_id(service))
    assert (file["state"], file["reasons"]) == ("with_specialist", [reason])


def test_a_text_pasted_from_a_web_page_is_still_credited() -> None:
    service, _ = make_service()
    case_id = active_id(service)
    service.answer("receiver", case_id, BROTHER_RECEIVER.replace("пәтер", "пә\u00adтер"))
    service.answer("sender", case_id, BROTHER_SENDER.replace("половина", "поло\u00adвина"))
    file = service.case_file(case_id)
    assert file["state"] == "credited"
    assert file["sender_answer"]["text"] == BROTHER_SENDER


def test_letters_typed_as_two_characters_stay_letters() -> None:
    decomposed = "мои\u0306 брат, е\u0308лка"
    assert clean_answer(decomposed) == "мой брат, ёлка"


# -- the clock ---------------------------------------------------------------------------


class Laptop:
    """A wall clock that somebody can set, and a steady counter."""

    def __init__(self) -> None:
        self.wall = START
        self.steady = 100.0

    def pass_time(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.steady += seconds

    def clock(self) -> SystemClock:
        return SystemClock(wall=lambda: self.wall, steady=lambda: self.steady)


def test_the_clock_follows_real_time() -> None:
    laptop = Laptop()
    clock = laptop.clock()
    laptop.pass_time(90)
    assert clock.now() == START + timedelta(seconds=90)


def test_time_goes_on_when_the_laptop_clock_is_set_back() -> None:
    laptop = Laptop()
    clock = laptop.clock()
    laptop.pass_time(60)
    before = clock.now()
    laptop.wall -= timedelta(minutes=10)
    assert clock.now() == before
    laptop.pass_time(5)
    assert clock.now() == before + timedelta(seconds=5)


def test_the_clock_follows_a_step_forward() -> None:
    # A laptop that slept: the steady counter may stand still, the wall clock does not.
    laptop = Laptop()
    clock = laptop.clock()
    laptop.wall += timedelta(hours=3)
    assert clock.now() == START + timedelta(hours=3)


def test_the_real_clock_is_in_bank_time() -> None:
    now = SystemClock().now()
    assert now.utcoffset() == timedelta(hours=5)
    assert abs(now - datetime.now(BANK_TIMEZONE)) < timedelta(seconds=5)


# -- the model list after a start without network --------------------------------------------


def wait_for_checks() -> None:
    for thread in threading.enumerate():
        if thread.name == "model-check":
            thread.join(timeout=5)


def setup_with(client: FakeGeminiClient) -> MatcherSetup:
    return build_matcher(offline=False, env={"GEMINI_API_KEY": "unit-test-key-value"}, client_factory=lambda key: client)


class NotFoundError(Exception):
    """Named like the class of the SDK."""


def test_the_list_is_asked_again_when_the_first_check_failed() -> None:
    def reply(request: dict[str, object]) -> object:
        return gemini_reply() if request["model"] == "gemini-3.6-flash" else NotFoundError("no such model")

    client = FakeGeminiClient(reply, models=RuntimeError("network down"))
    setup = setup_with(client)
    setup.confirm_model()
    assert setup.status().model_state == "unconfirmed"
    client.models.names = ["gemini-3.6-flash"]
    assert setup.matcher.compare("брат аренда", "брату аренда").fallback_code == "model_not_found"
    wait_for_checks()
    assert (setup.status().model, setup.status().model_state) == ("gemini-3.6-flash", "replaced")
    assert setup.matcher.compare("брат аренда", "брату аренда").fallback_code == ""


def test_a_good_answer_also_confirms_the_model_later() -> None:
    client = FakeGeminiClient(gemini_reply(), models=RuntimeError("network down"))
    setup = setup_with(client)
    setup.confirm_model()
    client.models.names = ["gemini-3.8-flash"]
    setup.matcher.compare("брат аренда", "брату аренда")
    wait_for_checks()
    assert setup.status().model_state == "confirmed"


def test_a_confirmed_model_is_not_checked_again() -> None:
    client = FakeGeminiClient(gemini_reply(), models=["gemini-3.8-flash"])
    setup = setup_with(client)
    setup.confirm_model()
    client.models.names = AssertionError("asked again")
    setup.matcher.compare("брат аренда", "брату аренда")
    wait_for_checks()
    assert setup.status().model_state == "confirmed"


# -- the start banner ----------------------------------------------------------------------------


@pytest.mark.parametrize(("host", "shown"), [("192.168.1.54", "192.168.1.54"), ("127.0.0.1", "127.0.0.1"), ("localhost", "localhost")])
def test_links_use_the_address_that_is_open(host: str, shown: str) -> None:
    text = banner(make_settings(host=host), 8191, MatcherStatus(active="offline", reason="forced"), ("10.0.0.7",))
    assert f"http://{shown}:8191/start" in text
    assert ("On real phones" in text) is (host == "192.168.1.54")
    assert "10.0.0.7" not in text


# -- .env files ------------------------------------------------------------------------------------


def read_env(path: Path, data: bytes) -> dict[str, str]:
    path.write_bytes(data)
    env: dict[str, str] = {}
    load_env_file(path, env)
    return env


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("demo-pass-2026   # for the jury", "demo-pass-2026"),
        ("demo-pass#2026", "demo-pass#2026"),
        ('"demo pass # 2026"  # quoted', "demo pass # 2026"),
        ("'demo pass'", "demo pass"),
        ("'unclosed", "'unclosed"),
    ],
)
def test_comments_do_not_become_part_of_a_value(tmp_path: Path, line: str, value: str) -> None:
    env = read_env(tmp_path / ".env", f"BOTHSIDES_STAFF_PASSWORD={line}\n".encode())
    assert env == {"BOTHSIDES_STAFF_PASSWORD": value}


def test_a_comment_alone_is_an_empty_value(tmp_path: Path) -> None:
    assert read_env(tmp_path / ".env", b"GEMINI_API_KEY= # my key comes here\n") == {}


@pytest.mark.parametrize("encoding", ["utf-16", "utf-8-sig", "utf-8"])
def test_files_of_windows_programs_are_read(tmp_path: Path, encoding: str) -> None:
    text = "# ключ\r\nGEMINI_API_KEY=abc\r\n"
    assert read_env(tmp_path / ".env", text.encode(encoding)) == {"GEMINI_API_KEY": "abc"}


def test_another_encoding_is_explained(tmp_path: Path) -> None:
    with pytest.raises(SettingsError) as caught:
        read_env(tmp_path / ".env", "# ключ\nGEMINI_API_KEY=abc\n".encode("cp1251"))
    assert "UTF-8" in str(caught.value)
    assert "abc" not in str(caught.value)
