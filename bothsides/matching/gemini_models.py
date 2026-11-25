"""Checks that the wanted model is on Google's list, or picks another Flash model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

#: Plain text models only: no tts, image, live or preview variants.
_FLASH = re.compile(r"gemini-(\d+)(?:\.(\d+))?-flash(-lite)?")

#: Asked for only when no plain name is listed: "gemini-flash-latest", "gemini-3-flash-preview", "...-001".
_FLASH_VARIANT = re.compile(r"gemini-(?:(\d+)(?:\.(\d+))?-)?flash(-lite)?-(?:latest|preview(?:-\d{2}-\d{4})?|\d{3})")


_LATEST = 99
_SPARES = 3


class ModelState(str, Enum):
    """What is known about the model in use."""

    CHECKING = "checking"
    CONFIRMED = "confirmed"
    REPLACED = "replaced"
    UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """The model to use and how sure we are that it exists."""

    model: str
    state: ModelState


def list_flash_names(client: Any) -> tuple[str, ...]:
    """Names of the listed models that can generate text, without "models/"."""
    names = []
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None)
        if actions and "generateContent" not in actions:
            continue
        names.append((getattr(model, "name", "") or "").removeprefix("models/"))
    return tuple(name for name in names if name)


def _rank(name: str, pattern: re.Pattern[str]) -> tuple[bool, int, int] | None:
    found = pattern.fullmatch(name)
    if not found:
        return None
    # "gemini-flash-latest" names no version: it is the newest one.
    return (found.group(3) is None, int(found.group(1) or _LATEST), int(found.group(2) or 0))


def _newest(names: tuple[str, ...], pattern: re.Pattern[str]) -> str | None:
    ranked = [(rank, name) for name in names if (rank := _rank(name, pattern)) is not None]
    return max(ranked)[1] if ranked else None


def spare_models(listed: Iterable[str], used: str) -> tuple[str, ...]:
    """Other listed Flash models with the same settings (Gemini 3 and later): the newest light one, then the newest ones.

    A light model is rarely overloaded together with the others.
    """
    ranked = sorted(
        ((rank, name) for name in set(listed) if name != used and (rank := _rank(name, _FLASH)) is not None and rank[1] >= 3),
        key=lambda item: (item[0][1], item[0][2], item[0][0]),
        reverse=True,
    )
    light = [name for rank, name in ranked if not rank[0]][:1]
    return (*light, *(name for _, name in ranked if name not in light))[:_SPARES]


def choose_model(listed: Iterable[str], wanted: str) -> ModelChoice:
    """Keep the wanted model if it is listed, else take the newest listed Flash model."""
    names = tuple(listed)
    if wanted in names:
        return ModelChoice(wanted, ModelState.CONFIRMED)
    other = _newest(names, _FLASH) or _newest(names, _FLASH_VARIANT)
    if other is None:
        return ModelChoice(wanted, ModelState.UNCONFIRMED)
    return ModelChoice(other, ModelState.REPLACED)
