"""Turns the downloaded Flow clips and stills into small web files: MP4, WebM and WebP.

    python landing-media/build_media.py              build everything in plan.json that is missing
    python landing-media/build_media.py --force      build everything again
    python landing-media/build_media.py --only a-hero-16x9
    python landing-media/build_media.py --posters    only the pictures, from the finished videos

Needs: pip install imageio-ffmpeg. Reads the originals from FLOW_OUT (default: flow-mcp-out
in the home folder) and writes public/assets/landing/ and manifest.json next to this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public" / "assets" / "landing"
FLOW_OUT = Path(os.environ.get("FLOW_OUT", Path.home() / "flow-mcp-out"))
SIZES = {"16x9": (1280, 720), "9x16": (720, 1280)}
MIN_FREE_BYTES = 60 * 1024 * 1024
WHOLE = (0.0, 0.0, 1.0, 1.0)
H264 = ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-x264-params", "aq-mode=3", "-movflags", "+faststart"]
VP9 = ["-c:v", "libvpx-vp9", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
WEBP = ["-c:v", "libwebp", "-quality", "80"]


class MediaError(RuntimeError):
    """A file could not be built; the message says which one and why."""


@dataclass(frozen=True, slots=True)
class Item:
    """One deliverable of plan.json."""

    id: str
    aspect: str
    sources: tuple[str, ...]
    #: "still", "cut", "loop" (tail fades into head) or "join" (clips one after another).
    edit: str
    use: str
    overlap: float = 1.0
    start: float = 0.0
    end: float | None = None
    #: Part of the picture that is kept: left, top, width, height as fractions.
    crop: tuple[float, float, float, float] = WHOLE
    crf_mp4: int = 27
    crf_webm: int = 37

    @property
    def name(self) -> str:
        return f"{self.id}-{self.aspect}"


def ffmpeg() -> str:
    """Path of ffmpeg: the one on PATH, or the one shipped with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise MediaError("ffmpeg not found: pip install imageio-ffmpeg") from error
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(arguments: Sequence[str]) -> str:
    """Run ffmpeg and return what it printed."""
    result = subprocess.run([ffmpeg(), "-hide_banner", "-y", *arguments], capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise MediaError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "ffmpeg failed")
    return result.stderr


def seconds(path: Path) -> float:
    """Length of the picture track, counted from its frames (the sound is often longer)."""
    log = run(["-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "null", "-"])
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", log)
    if not times:
        raise MediaError(f"cannot read the length of {path.name}")
    hours, minutes, rest = times[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def _scaled(label: str, item: Item, out: str) -> str:
    width, height = SIZES[item.aspect]
    left, top, wide, high = item.crop
    cut = f"crop=iw*{wide}:ih*{high}:iw*{left}:ih*{top}"
    fit = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}"
    return f"[{label}]{cut},{fit},setsar=1,format=yuv420p[{out}]"


def loop_graph(item: Item, length: float) -> str:
    """The tail fades into the head, so the last frame is followed by the first one."""
    end = item.end or length
    body = end - item.start
    if body <= 2 * item.overlap:
        raise MediaError(f"{item.name}: too short to loop with an overlap of {item.overlap} s")
    cut, offset = item.start + item.overlap, body - 2 * item.overlap
    return ";".join(
        [
            "[0:v]split[s0][s1]",
            f"[s0]trim={cut:.3f}:{end:.3f},setpts=PTS-STARTPTS[main]",
            f"[s1]trim={item.start:.3f}:{cut:.3f},setpts=PTS-STARTPTS[head]",
            f"[main][head]xfade=transition=fade:duration={item.overlap:.3f}:offset={offset:.3f}[joined]",
            _scaled("joined", item, "v"),
        ]
    )


def cut_graph(item: Item, length: float) -> str:
    """One clip, optionally trimmed at both ends."""
    end = item.end or length
    return ";".join([f"[0:v]trim={item.start:.3f}:{end:.3f},setpts=PTS-STARTPTS[cut]", _scaled("cut", item, "v")])


def join_graph(item: Item, lengths: Sequence[float]) -> str:
    """Several clips one after another, each joined with a short fade."""
    steps, label, total = [], "0:v", lengths[0]
    for index, length in enumerate(lengths[1:], start=1):
        offset = total - item.overlap
        steps.append(f"[{label}][{index}:v]xfade=transition=fade:duration={item.overlap:.3f}:offset={offset:.3f}[j{index}]")
        label, total = f"j{index}", total + length - item.overlap
    return ";".join([*steps, _scaled(label, item, "v")])


def graph(item: Item, paths: Sequence[Path]) -> str:
    lengths = [seconds(path) for path in paths]
    if item.edit == "loop":
        return loop_graph(item, lengths[0])
    if item.edit == "join":
        return join_graph(item, lengths)
    if item.edit == "cut":
        return cut_graph(item, lengths[0])
    raise MediaError(f"{item.name}: unknown edit {item.edit!r}")


def _picture(source: Path, name: str) -> None:
    """The first frame as WebP."""
    run(["-i", str(source), "-frames:v", "1", *WEBP, str(PUBLIC / f"{name}.webp")])


def _last_picture(source: Path, name: str) -> None:
    """The last frame as WebP: shown to people who asked for less motion."""
    run(["-sseof", "-0.5", "-i", str(source), "-vf", "reverse", "-frames:v", "1", *WEBP, str(PUBLIC / f"{name}-end.webp")])


def pictures(item: Item) -> None:
    """Write the poster of a video; a clip that does not loop also gets its last frame."""
    video = PUBLIC / f"{item.name}.mp4"
    if not video.is_file():
        return
    _picture(video, item.name)
    if item.edit != "loop":
        _last_picture(video, item.name)


def build(item: Item) -> None:
    """Write the MP4, the WebM and the poster of one item; a still is only a picture."""
    if shutil.disk_usage(HERE).free < MIN_FREE_BYTES:
        raise MediaError("less than 60 MB free on the disk: nothing was written")
    paths = [FLOW_OUT / source for source in item.sources]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise MediaError(f"{item.name}: missing {', '.join(missing)}")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    if item.edit == "still":
        _picture(paths[0], item.name)
        return
    inputs = [part for path in paths for part in ("-i", str(path))]
    tail = ["-filter_complex", graph(item, paths), "-map", "[v]", "-an", "-g", "48"]
    run([*inputs, *tail, *H264, "-crf", str(item.crf_mp4), str(PUBLIC / f"{item.name}.mp4")])
    run([*inputs, *tail, *VP9, "-crf", str(item.crf_webm), str(PUBLIC / f"{item.name}.webm")])
    pictures(item)


def load_plan() -> tuple[list[Item], dict[str, Any]]:
    """Read plan.json: the deliverables and the facts repeated in the manifest."""
    data = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    items = [
        Item(**{**entry, "sources": tuple(entry["sources"]), "crop": tuple(entry.get("crop", WHOLE))})
        for entry in data["items"]
    ]
    names = [item.name for item in items]
    if len(names) != len(set(names)):
        raise MediaError("plan.json names one deliverable twice")
    return items, data


def _file_facts(path: Path) -> dict[str, Any]:
    return {
        "file": path.relative_to(HERE).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def describe(item: Item) -> dict[str, Any]:
    """The manifest entry of one item."""
    built = [path for end in (".mp4", ".webm", ".webp", "-end.webp") if (path := PUBLIC / f"{item.name}{end}").is_file()]
    video = next((path for path in built if path.suffix == ".mp4"), None)
    return {
        "id": item.id,
        "aspect": item.aspect,
        "use": item.use,
        "edit": item.edit,
        "seconds": round(seconds(video), 2) if video else None,
        "sources": list(item.sources),
        "files": [_file_facts(path) for path in built],
    }


def write_manifest(items: Sequence[Item], data: dict[str, Any]) -> None:
    facts = {key: value for key, value in data.items() if key != "items"}
    manifest = {**facts, "files": [describe(item) for item in items]}
    text = json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    (HERE / "manifest.json").write_text(text, encoding="utf-8", newline="\n")


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the web files of the landing page.")
    parser.add_argument("--force", action="store_true", help="build files that already exist")
    parser.add_argument("--only", default="", help="one deliverable, for example a-hero-16x9")
    parser.add_argument("--posters", action="store_true", help="write only the pictures of the finished videos")
    parsed = parser.parse_args(list(arguments))
    items, data = load_plan()
    failures = 0
    for item in items:
        if parsed.only and item.name != parsed.only:
            continue
        if not (parsed.force or parsed.posters) and (PUBLIC / f"{item.name}.webp").is_file():
            continue
        try:
            (pictures if parsed.posters else build)(item)
            print(f"built {item.name}", flush=True)
        except MediaError as error:
            failures += 1
            print(f"FAILED {item.name}: {error}", flush=True)
    write_manifest(items, data)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
