"""The route table and the handlers behind it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from .. import config
from ..cases.tryout import try_answers
from ..demo.scenes import SCENES, Scene
from . import static
from .auth import LoginFailed, LoginLocked
from .messages import HttpError, Response, json_response, redirect

if TYPE_CHECKING:
    from .app import App
    from .messages import Request

SESSION_COOKIE = "bs_staff"
_COOKIE_FLAGS = "Path=/; HttpOnly; SameSite=Strict"


@dataclass(frozen=True, slots=True)
class Context:
    """What a handler gets."""

    app: "App"
    request: "Request"
    params: dict[str, str]
    data: dict[str, Any]

    def field(self, name: str) -> str:
        """Return a text field of the request body."""
        value = self.data.get(name)
        if not isinstance(value, str):
            raise HttpError(400, "bad_field")
        return value


Handler = Callable[[Context], Response]


@dataclass(frozen=True, slots=True)
class Route:
    """One method and path. ``staff`` routes need a session."""

    method: str
    pattern: re.Pattern[str]
    handler: Handler
    staff: bool = False
    page: bool = False


# -- pages ---------------------------------------------------------------------


def _root(context: Context) -> Response:
    """The landing page, or the app when only the app is built."""
    landing = static.page(context.app.web_root, "index.html")
    return landing if landing.status == 200 else redirect(302, "/start")


def _app_page(context: Context) -> Response:
    return static.page(context.app.web_root, "app.html")


def _asset(context: Context) -> Response:
    found = static.asset(context.app.web_root, context.request.path, context.request.headers.get("range", ""))
    if found is None:
        raise HttpError(404, "not_found")
    return found


# -- public API ------------------------------------------------------------------


def _status(context: Context) -> Response:
    status = context.app.setup.status()
    return json_response(
        {
            "matcher": {
                "active": status.active,
                "reason": status.reason,
                "model": status.model,
                "model_state": status.model_state,
            }
        }
    )


def _try(context: Context) -> Response:
    """The mini-demo of the landing page: no language model, nothing is stored."""
    return json_response(try_answers(context.field("receiver"), context.field("sender")).view())


def _phone(context: Context) -> Response:
    return json_response(context.app.service.phone(context.params["side"]))


def _answer(context: Context) -> Response:
    case_id, text = context.field("case_id"), context.field("text")
    return json_response(context.app.service.answer(context.params["side"], case_id, text))


def _deny(context: Context) -> Response:
    return json_response(context.app.service.tap_deny(context.field("case_id")))


def _accept_return(context: Context) -> Response:
    return json_response(context.app.service.accept_return(context.field("case_id")))


def _objection(context: Context) -> Response:
    case_id = context.field("case_id")
    return json_response(context.app.service.object(context.params["side"], case_id))


# -- login -------------------------------------------------------------------------


def _cookie(value: str, max_age: int) -> tuple[str, str]:
    return ("Set-Cookie", f"{SESSION_COOKIE}={value}; {_COOKIE_FLAGS}; Max-Age={max_age}")


def _login(context: Context) -> Response:
    try:
        token = context.app.auth.login(context.field("password"), context.request.address)
    except LoginLocked as locked:
        raise HttpError(429, "locked", (("Retry-After", str(locked.seconds)),)) from None
    except LoginFailed:
        raise HttpError(401, "wrong_password") from None
    max_age = int(config.SESSION_LIFETIME.total_seconds())
    return json_response({"staff": True}, headers=(_cookie(token, max_age),))


def _logout(context: Context) -> Response:
    context.app.auth.logout(context.app.session_token(context.request))
    return json_response({"staff": False}, headers=(_cookie("", 0),))


def _session(context: Context) -> Response:
    return json_response({"staff": context.app.is_staff(context.request)})


# -- staff API -----------------------------------------------------------------------


def _scene_view(scene: Scene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "receiver_script": scene.receiver_script,
        "sender_script": scene.sender_script,
    }


def _stage(context: Context) -> Response:
    return json_response(context.app.service.stage())


def _cases(context: Context) -> Response:
    return json_response(context.app.service.cases())


def _case_file(context: Context) -> Response:
    return json_response(context.app.service.case_file(context.params["id"]))


def _close_case(context: Context) -> Response:
    return json_response(context.app.service.close_case(context.params["id"], context.params["action"]))


def _scenes(context: Context) -> Response:
    stage = context.app.service.stage()
    scenes = [_scene_view(scene) for scene in SCENES]
    return json_response({"active": stage["scene"], "case_id": stage["case"]["id"], "scenes": scenes})


def _start_scene(context: Context) -> Response:
    return json_response(context.app.service.start_scene(context.params["scene"]))


def _reset(context: Context) -> Response:
    return json_response(context.app.service.reset())


def _matcher(context: Context) -> Response:
    status = context.app.setup.status()
    return json_response(
        {
            "active": status.active,
            "reason": status.reason,
            "model": status.model,
            "model_state": status.model_state,
            "last_failure": status.last_failure,
        }
    )


# -- table -----------------------------------------------------------------------------


def _route(method: str, pattern: str, handler: Handler, staff: bool = False, page: bool = False) -> Route:
    return Route(method, re.compile(pattern), handler, staff, page)


_CASE = r"/api/cases/(?P<id>BS-\d{4}-\d{4,6})"

ROUTES: tuple[Route, ...] = (
    _route("GET", r"/", _root),
    _route("GET", r"/(?:start|receiver|sender|login)", _app_page),
    _route("GET", r"/(?:stage|console|demo)", _app_page, staff=True, page=True),
    _route("GET", r"/console/BS-\d{4}-\d{4,6}", _app_page, staff=True, page=True),
    _route("GET", r"/assets/.+", _asset),
    _route("GET", r"/api/status", _status),
    _route("POST", r"/api/try", _try),
    _route("GET", r"/api/phone/(?P<side>receiver|sender)", _phone),
    _route("POST", r"/api/phone/(?P<side>receiver|sender)/answer", _answer),
    _route("POST", r"/api/phone/(?P<side>receiver|sender)/objection", _objection),
    _route("POST", r"/api/phone/receiver/deny", _deny),
    _route("POST", r"/api/phone/receiver/accept-return", _accept_return),
    _route("POST", r"/api/login", _login),
    _route("POST", r"/api/logout", _logout),
    _route("GET", r"/api/session", _session),
    _route("GET", r"/api/stage", _stage, staff=True),
    _route("GET", r"/api/cases", _cases, staff=True),
    _route("GET", _CASE, _case_file, staff=True),
    _route("POST", _CASE + r"/(?P<action>release|return)", _close_case, staff=True),
    _route("GET", r"/api/scenes", _scenes, staff=True),
    _route("POST", r"/api/scenes/(?P<scene>[a-z]{1,20})/start", _start_scene, staff=True),
    _route("POST", r"/api/reset", _reset, staff=True),
    _route("GET", r"/api/matcher", _matcher, staff=True),
)


def find_route(method: str, path: str) -> tuple[Route, dict[str, str]]:
    """Return the route and its parameters, or raise 404 / 405."""
    allowed: list[str] = []
    for route in ROUTES:
        found = route.pattern.fullmatch(path)
        if not found:
            continue
        if route.method == method:
            return route, found.groupdict()
        allowed.append(route.method)
    if allowed:
        raise HttpError(405, "bad_method", (("Allow", ", ".join(sorted(set(allowed)))),))
    raise HttpError(404, "not_found")
