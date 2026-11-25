"""The workflow around one shared board. All changes happen under one lock."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, Protocol

from .. import config
from ..clock import Clock
from ..decision.stories import Story, similar_receivers
from ..demo.scenes import SCENES, Scene
from ..demo.seed import background_cases, case_number, open_scene
from ..matching.types import Matcher, MatcherError, MatchResult
from ..textnorm import clean, one_line
from . import transitions, views
from .errors import empty_answer, not_found, stale_case, too_long
from .model import Board, Case, CaseState, Side

_LOG = logging.getLogger(__name__)

_STAFF_ACTIONS = {"release": CaseState.CREDITED, "return": CaseState.RETURNED}


class Executor(Protocol):
    """Runs the comparison somewhere, so that a phone does not wait for it."""

    def submit(self, work: Callable[[], None]) -> None: ...


class ThreadExecutor:
    """One daemon thread per comparison."""

    def submit(self, work: Callable[[], None]) -> None:
        threading.Thread(target=work, name="comparison", daemon=True).start()


def clean_answer(text: str) -> str:
    """Return the answer as one tidy line, or raise a ServiceError."""
    # Checked again after composing: one character may stand for eighteen.
    if len(text) > config.MAX_ANSWER_LENGTH or len(clean(text)) > config.MAX_ANSWER_LENGTH:
        raise too_long()
    tidy = one_line(text)
    if len(tidy) < config.MIN_ANSWER_LENGTH:
        raise empty_answer()
    return tidy


def _side(name: str) -> Side:
    try:
        return Side(name)
    except ValueError:
        raise not_found() from None


def _scene(scene_id: str) -> Scene:
    found = next((scene for scene in SCENES if scene.id == scene_id), None)
    if found is None:
        raise not_found()
    return found


class CaseService:
    """Everything the screens can ask for or do."""

    def __init__(
        self, clock: Clock, matcher: Matcher, executor: Executor | None = None, first_number: int = 1
    ) -> None:
        self._clock = clock
        self._matcher = matcher
        self._executor = executor or ThreadExecutor()
        self._lock = threading.RLock()
        self._board = self._fresh_board(first_number)

    # -- board ----------------------------------------------------------------

    def _fresh_board(self, first_number: int) -> Board:
        now = self._clock.now()
        cases, stories, number = background_cases(now, first_number)
        active = open_scene(SCENES[0], case_number(now, number), now)
        return Board(
            cases=(active, *cases), active_id=active.id, stories=stories, next_number=number + 1
        )

    def _current(self) -> tuple[Board, datetime]:
        """Return the board with passed deadlines applied. Call under the lock."""
        now = self._clock.now()
        expired = tuple(transitions.expire(case, now) for case in self._board.cases)
        if expired != self._board.cases:
            self._board = replace(self._board, cases=expired)
        return self._board, now

    def _active_case(self, case_id: str) -> tuple[Board, Case, datetime]:
        board, now = self._current()
        if case_id != board.active_id:
            raise stale_case()
        return board, board.active, now

    def _any_case(self, case_id: str) -> tuple[Board, Case, datetime]:
        board, now = self._current()
        case = board.find(case_id)
        if case is None:
            raise not_found()
        return board, case, now

    # -- phones ---------------------------------------------------------------

    def phone(self, side_name: str) -> dict[str, Any]:
        """The customer view of the active case."""
        side = _side(side_name)
        with self._lock:
            board, now = self._current()
            return views.phone_view(board.active, side, now)

    def answer(self, side_name: str, case_id: str, text: str) -> dict[str, Any]:
        """Take an answer; after the second one compare both."""
        side = _side(side_name)
        tidy = clean_answer(text)
        with self._lock:
            board, case, now = self._active_case(case_id)
            if side is Side.RECEIVER:
                changed = transitions.submit_receiver_answer(case, tidy, now)
                self._board = board.with_case(changed)
            else:
                receiver_id = case.transfer.receiver.id
                similar = similar_receivers(board.stories, receiver_id, tidy, now)
                changed = transitions.note_similar(transitions.submit_sender_answer(case, tidy, now), similar)
                story = Story(receiver_id, tidy, now, case.id)
                self._board = board.with_case(changed).with_story(story)
        if changed.state is CaseState.COMPARING:
            self._executor.submit(lambda: self._compare(changed))
        return self.phone(side_name)

    def tap_deny(self, case_id: str) -> dict[str, Any]:
        """"I do not know this person": two taps within four seconds."""
        with self._lock:
            board, case, now = self._active_case(case_id)
            self._board = board.with_case(transitions.tap_deny(case, now))
        return self.phone(Side.RECEIVER.value)

    def accept_return(self, case_id: str) -> dict[str, Any]:
        """The receiver agrees that the money goes back."""
        with self._lock:
            board, case, now = self._active_case(case_id)
            self._board = board.with_case(transitions.accept_return(case, now))
        return self.phone(Side.RECEIVER.value)

    def object(self, side_name: str, case_id: str) -> dict[str, Any]:
        """A client objects to a hold."""
        side = _side(side_name)
        with self._lock:
            board, case, now = self._active_case(case_id)
            self._board = board.with_case(transitions.object_to_hold(case, side, now))
        return self.phone(side_name)

    # -- comparison -------------------------------------------------------------

    def _score(self, case: Case) -> MatchResult | None:
        if case.receiver_answer is None or case.sender_answer is None:
            return None
        try:
            return self._matcher.compare(case.receiver_answer.text, case.sender_answer.text)
        except MatcherError as error:
            _LOG.warning("no matcher answered: %s", error.code)
        except Exception as error:
            _LOG.error("matcher failed: %s", type(error).__name__)
        return None

    def _compare(self, asked: Case) -> None:
        match = self._score(asked)
        with self._lock:
            board, now = self._current()
            case = board.find(asked.id)
            if case is None or case.state is not CaseState.COMPARING or case.sender_answer is None:
                return
            receiver_id = case.transfer.receiver.id
            similar = similar_receivers(board.stories, receiver_id, case.sender_answer.text, now)
            self._board = board.with_case(transitions.apply_comparison(case, match, similar, now))

    # -- staff ----------------------------------------------------------------

    def stage(self) -> dict[str, Any]:
        """The big screen."""
        with self._lock:
            board, now = self._current()
            return views.stage_view(board.active, now)

    def cases(self) -> dict[str, Any]:
        """The console list, newest transfer first."""
        with self._lock:
            board, now = self._current()
            ordered = sorted(board.cases, key=lambda case: case.stopped_at, reverse=True)
            return {
                "active_id": board.active_id,
                "cases": [views.case_summary(case, now) for case in ordered],
            }

    def case_file(self, case_id: str) -> dict[str, Any]:
        """One case in full."""
        with self._lock:
            _, case, now = self._any_case(case_id)
            return views.case_file(case, now)

    def close_case(self, case_id: str, action: str) -> dict[str, Any]:
        """A specialist releases or returns the money."""
        state = _STAFF_ACTIONS.get(action)
        if state is None:
            raise not_found()
        with self._lock:
            board, case, now = self._any_case(case_id)
            closed = transitions.close_by_staff(case, state, now)
            self._board = board.with_case(closed)
            return views.case_file(closed, now)

    # -- demo -----------------------------------------------------------------

    def start_scene(self, scene_id: str) -> dict[str, Any]:
        """Open this scene again; its earlier case and story are forgotten."""
        scene = _scene(scene_id)
        with self._lock:
            board, now = self._current()
            dropped = {case.id for case in board.cases if case.scene == scene.id}
            opened = open_scene(scene, case_number(now, board.next_number), now)
            self._board = Board(
                cases=(opened, *(case for case in board.cases if case.id not in dropped)),
                active_id=opened.id,
                stories=tuple(story for story in board.stories if story.case_id not in dropped),
                next_number=board.next_number + 1,
            )
            return views.stage_view(opened, now)

    def reset(self) -> dict[str, Any]:
        """Back to the first scene with a clean board. Case numbers go on."""
        with self._lock:
            self._board = self._fresh_board(self._board.next_number)
            return views.stage_view(self._board.active, self._clock.now())

