"""Checks on the interface that need no Node: texts, colours, the built files."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ROOT / "frontend" / "src" / "i18n"
CSS = ROOT / "frontend" / "src" / "styles" / "index.css"
WEB = ROOT / "web"


def load(lang: str) -> dict[str, str]:
    return json.loads((TEXTS / f"{lang}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("lang", ["kk", "en"])
def test_every_language_has_every_text(lang: str) -> None:
    russian, other = load("ru"), load(lang)
    assert list(russian) == list(other)
    for key, text in russian.items():
        assert set(re.findall(r"\{\w+\}", text)) == set(re.findall(r"\{\w+\}", other[key])), key
        assert other[key].strip(), key


def test_kazakh_texts_are_kazakh() -> None:
    letters = set("әғқңөұүһі")
    texts = [text for key, text in load("kk").items() if len(text) > 25]
    share = sum(1 for text in texts if letters & set(text.lower())) / len(texts)
    assert share > 0.95


@pytest.mark.parametrize("lang", ["ru", "kk", "en"])
def test_the_hint_names_the_seconds_of_the_config(lang: str) -> None:
    from bothsides import config

    seconds = int(config.DENY_CONFIRM_WINDOW.total_seconds())
    assert re.findall(r"\d+", load(lang)["phone.deny_confirm"]) == [str(seconds)]


def test_every_text_is_used() -> None:
    source = "".join(
        file.read_text(encoding="utf-8")
        for pattern in ("*.ts", "*.tsx")
        for file in (ROOT / "frontend" / "src").rglob(pattern)
    )
    prefixes = set(re.findall(r"`([a-z_]+(?:\.[a-z_]+)*\.)\$\{", source))
    unused = [
        key
        for key in load("ru")
        if not re.search(f"['\"]{re.escape(key)}['\"]", source) and not any(key.startswith(prefix) for prefix in prefixes)
    ]
    assert unused == []


def test_every_code_of_the_server_has_a_text() -> None:
    from bothsides.cases.model import CaseState
    from bothsides.decision.reasons import ReasonCode
    from bothsides.demo.scenes import SCENES

    texts = load("ru")
    expected = [f"reason.{code.value}" for code in ReasonCode]
    expected += [f"status.{state.value}" for state in CaseState]
    expected += [f"scene.{scene.id}.name" for scene in SCENES] + [f"scene.{scene.id}.text" for scene in SCENES]
    source = (ROOT / "bothsides" / "cases" / "transitions.py").read_text(encoding="utf-8")
    events = set(re.findall(r'"((?:transfer|receiver|sender|decided|return|staff)_[a-z]+|compared|objection)"', source))
    expected += [f"event.{event}" for event in events]
    assert len(events) >= 14
    assert [key for key in expected if key not in texts] == []


# -- contrast ---------------------------------------------------------------------


def _themes() -> dict[str, dict[str, str]]:
    css = CSS.read_text(encoding="utf-8")
    light = css[css.index(":root {") : css.index("@media (prefers-color-scheme: dark)")]
    dark = css[css.index("@media (prefers-color-scheme: dark)") : css.index("@theme inline")]
    pattern = re.compile(r"--([a-z-]+):\s*(#[0-9a-f]{6})")
    return {"light": dict(pattern.findall(light)), "dark": dict(pattern.findall(dark))}


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


TEXT_PAIRS = [
    ("text", "bg"),
    ("text", "surface"),
    ("text", "sunken"),
    ("muted", "bg"),
    ("muted", "surface"),
    ("muted", "sunken"),
    ("text", "line"),
    ("accent", "surface"),
    ("accent", "bg"),
    ("accent", "sunken"),
    ("accent", "line"),
    ("surface", "accent"),
    ("on-action", "action"),
    ("on-action", "action-strong"),
    *[(front, back) for front in ("on-hero", "on-hero-muted") for back in ("hero", "hero-deep", "hero-glow", "hero-chip")],
    ("surface", "text"),
    *[(name, f"{name}-soft") for name in ("credited", "specialist", "held", "returned")],
    *[(name, "surface") for name in ("credited", "specialist", "held", "returned")],
    *[(name, "bg") for name in ("credited", "specialist", "held", "returned")],
    *[("surface", name) for name in ("credited", "held", "returned")],
    ("on-specialist", "specialist-fill"),
    *[("text", f"{name}-soft") for name in ("credited", "specialist")],
    ("muted", "credited-soft"),
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("front", "back"), TEXT_PAIRS)
def test_text_contrast_meets_wcag_aa(theme: str, front: str, back: str) -> None:
    colors = _themes()[theme]
    assert contrast(colors[front], colors[back]) >= 4.5, (theme, front, back)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_controls_meet_wcag_for_non_text(theme: str) -> None:
    colors = _themes()[theme]
    assert contrast(colors["line-strong"], colors["surface"]) >= 3.0
    # The focus ring, and the chosen option of a group against the others.
    for front, back in (("accent", "surface"), ("accent", "bg"), ("action", "hero"), ("action", "hero-glow")):
        assert contrast(colors[front], colors[back]) >= 3.0, (theme, front, back)
    for front, back in (("action", "hero-chip"), ("text", "sunken")):
        assert contrast(colors[front], colors[back]) >= 3.0, (theme, front, back)


def test_status_colours_are_not_used_for_anything_else() -> None:
    """The accent and the action differ from every status, also from "credited"."""
    for theme, colors in _themes().items():
        statuses = {colors[name] for name in ("credited", "specialist", "held", "returned")}
        assert not statuses & {colors["accent"], colors["action"], colors["hero"]}, theme


#: Where the colour of a status may be used. Red also marks a denial.
STATUS_COLOUR_FILES = {
    "credited": {"status.tsx", "verdict.ts"},
    "specialist": {"status.tsx", "verdict.ts"},
    "held": {"status.tsx", "verdict.ts", "ui.tsx", "Reasons.tsx", "StagePhone.tsx", "ConsolePage.tsx"},
    "returned": {"status.tsx"},
}


@pytest.mark.parametrize("status", sorted(STATUS_COLOUR_FILES))
def test_status_colours_stay_with_the_statuses(status: str) -> None:
    pattern = re.compile(rf"(?<![\w-])(?:[a-z-]+:)*(?:bg|text|ring|border|outline|fill)-(?:on-)?{status}\b")
    files = [file for kind in ("*.ts", "*.tsx") for file in (ROOT / "frontend" / "src").rglob(kind)]
    found = {file.name for file in files if pattern.search(file.read_text(encoding="utf-8"))}
    assert found == STATUS_COLOUR_FILES[status]


def test_every_colour_exists_in_both_themes() -> None:
    themes = _themes()
    assert set(themes["light"]) == set(themes["dark"])


# -- built files --------------------------------------------------------------------


PAGES = ["app.html", "index.html"]


@pytest.mark.parametrize("name", PAGES)
def test_build_is_in_the_project_and_has_no_inline_code(name: str) -> None:
    page = (WEB / name).read_text(encoding="utf-8")
    assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", page) == []
    assert "<style" not in page and "style=" not in page
    files = re.findall(r'(?:src|href)="(/assets/[^"]+)"', page)
    assert len(files) >= 3
    for file in files:
        assert (WEB / file.lstrip("/")).is_file(), file


def test_build_loads_nothing_from_the_internet() -> None:
    for file in (WEB / "assets").glob("*.css"):
        assert not re.search(r"url\((?!['\"]?(?:/assets|data:))", file.read_text(encoding="utf-8"))
    for name in PAGES:
        page = (WEB / name).read_text(encoding="utf-8")
        assert not re.search(r'(?:src|href)="https?:', page), name


def test_bank_name_is_not_in_the_app() -> None:
    """Only the landing page names the bank: it is about the case of the hackathon."""
    pattern = re.compile(r"BCC|БЦК|CenterCredit|ЦентрКредит", re.IGNORECASE)
    files = [WEB / "app.html", *(WEB / "assets").glob("app-*.js"), *TEXTS.glob("*.json")]
    assert len(files) == 5
    for file in files:
        assert not pattern.search(file.read_text(encoding="utf-8")), file.name


def test_reduced_motion_is_respected() -> None:
    assert "prefers-reduced-motion: reduce" in CSS.read_text(encoding="utf-8")


def test_kazakh_review_file_is_up_to_date() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "kazakh_texts.py"), "--check"], capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stdout
