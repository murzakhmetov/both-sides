"""Serves the built interface. Nothing outside the asset folder is reachable."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .messages import Headers, Response, text_response

#: Windows may map .js to text/plain in the registry, so types are fixed here.
_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".woff2": "font/woff2",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".json": "application/json; charset=utf-8",
}

#: One file name, optionally in subfolders; no dots at the start, no backslashes.
_ASSET = re.compile(r"/assets/((?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-][A-Za-z0-9._-]*)")
#: Built files have a hash in their name; files in subfolders keep their name when they change.
_LONG_CACHE = "public, max-age=31536000, immutable"
_SHORT_CACHE = "public, max-age=3600"

#: "bytes=first-last", "bytes=first-" or "bytes=-count": phones ask for a video in parts.
_RANGE = re.compile(r"bytes=(?:([0-9]{1,15})-([0-9]{0,15})|-([0-9]{1,15}))")

_NOT_BUILT = (
    "The interface is not built yet. Run once in the frontend folder:\n"
    "  npm install\n  npm run build\nThen start the server again.\n"
)


def page(web_root: Path, name: str, status: int = 200) -> Response:
    """Return a built HTML page."""
    try:
        body = (web_root / name).read_bytes()
    except OSError:
        return text_response(503, _NOT_BUILT)
    return Response(status, (("Content-Type", "text/html; charset=utf-8"),), body)


def _span(wanted: str, size: int) -> tuple[int, int] | None:
    """The first and the last byte of the asked part; None for the whole file.

    A part that lies behind the end starts at *size* or later.
    """
    found = _RANGE.fullmatch(wanted)
    if not found:
        return None
    first, last, count = found.groups()
    start = int(first) if first else max(0, size - int(count))
    end = min(int(last), size - 1) if last else size - 1
    return None if last and int(last) < start else (start, end)


def _file(path: Path, headers: Headers, wanted: str) -> Response:
    """A file or the asked part of it. Raises OSError when it cannot be read."""
    with path.open("rb") as file:
        size = os.fstat(file.fileno()).st_size
        span = _span(wanted, size)
        if span is None:
            return Response(200, headers, file.read())
        start, end = span
        if start >= size:
            return Response(416, (("Content-Range", f"bytes */{size}"),), b"")
        file.seek(start)
        body = file.read(end - start + 1)
    return Response(206, (*headers, ("Content-Range", f"bytes {start}-{end}/{size}")), body)


def asset(web_root: Path, path: str, wanted: str = "") -> Response | None:
    """Return a built asset or a part of it, or None when there is no such file."""
    found = _ASSET.fullmatch(path)
    if not found:
        return None
    root = (web_root / "assets").resolve()
    target = (root / found.group(1)).resolve()
    content_type = _TYPES.get(target.suffix.lower())
    if content_type is None or not target.is_relative_to(root) or not target.is_file():
        return None
    cache = _SHORT_CACHE if "/" in found.group(1) else _LONG_CACHE
    headers = (("Content-Type", content_type), ("Cache-Control", cache), ("Accept-Ranges", "bytes"))
    try:
        return _file(target, headers, wanted)
    except OSError:
        return None
