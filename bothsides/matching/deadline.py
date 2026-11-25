"""Runs a call with a hard wall-clock limit.

The SDK timeout applies to each network phase, so a slow reply can take longer
than the limit in total. This helper stops waiting on time, whatever happens.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable


class DeadlineExceeded(Exception):
    """The call did not finish in time."""


def call_with_deadline(work: Callable[[], Any], seconds: float) -> Any:
    """Return ``work()`` or raise :class:`DeadlineExceeded` after *seconds*.

    The worker is a daemon thread: a call that hangs does not block shutdown.
    """
    results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            results.put((True, work()))
        except Exception as error:  # handed over to the caller's thread
            results.put((False, error))

    threading.Thread(target=run, name="matcher-call", daemon=True).start()
    try:
        succeeded, value = results.get(timeout=seconds)
    except queue.Empty:
        raise DeadlineExceeded() from None
    if succeeded:
        return value
    raise value
