"""Loads the JSON word lists that the Python server and any port share."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=None)
def load_json(name: str) -> dict[str, Any]:
    """Read ``data/<name>.json`` once. Callers must not change the result."""
    path = DATA_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read the data file {path.name}: {error}") from error
