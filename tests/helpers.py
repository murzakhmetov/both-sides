"""Builders shared by the workflow tests."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from bothsides.cases.service import CaseService
from bothsides.config import BANK_TIMEZONE
from bothsides.matching.offline import OfflineMatcher
from bothsides.matching.types import Matcher

from .fakes import InlineExecutor, ManualClock

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2026, 11, 26, 12, 0, tzinfo=BANK_TIMEZONE)

BROTHER_RECEIVER = "ағам пәтер жалдау ақысының жартысын жіберді"
BROTHER_SENDER = "Брату, моя половина аренды квартиры"
SISTER_RECEIVER = "друг вернул долг"
SISTER_SENDER = "сестре на лечение"


def make_service(
    matcher: Matcher | None = None, clock: ManualClock | None = None, executor: Any = None
) -> tuple[CaseService, ManualClock]:
    used_clock = clock or ManualClock(START)
    service = CaseService(
        clock=used_clock,
        matcher=matcher or OfflineMatcher(),
        executor=executor or InlineExecutor(),
    )
    return service, used_clock


def active_id(service: CaseService) -> str:
    return service.stage()["case"]["id"]


def run_scene(service: CaseService, scene: str, receiver_text: str, sender_text: str) -> dict[str, Any]:
    service.start_scene(scene)
    case_id = active_id(service)
    service.answer("receiver", case_id, receiver_text)
    service.answer("sender", case_id, sender_text)
    return service.case_file(case_id)


def start_output(arguments: list[str], env: dict[str, str], cwd: Path, seconds: float = 30.0) -> tuple[bytes, bytes]:
    """Start run.py in its own process and read until it is ready. Never waits longer than *seconds*."""
    process = subprocess.Popen(
        [sys.executable, "-S", str(ROOT / "run.py"), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    limit = threading.Timer(seconds, process.kill)
    limit.start()
    try:
        seen = b""
        while b"Stop with Ctrl+C" not in seen:
            line = process.stdout.readline()  # type: ignore[union-attr]
            if not line:
                break
            seen += line
    finally:
        limit.cancel()
        process.kill()
        _, errors = process.communicate(timeout=10)
    return seen, errors


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
