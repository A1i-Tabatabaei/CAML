"""Repo-root discovery.

CAML's ``caml`` entrypoint is an installed console-script (unlike AMLB's
root-level ``runbenchmark.py``), so it can't infer its own repo root from
``__file__``. Instead we walk up from the current working directory looking
for the marker files that only exist at the CAML repo root.
"""

from __future__ import annotations

import os
from pathlib import Path

_MARKERS = ("pyproject.toml", "frameworks", "resources")


def find_repo_root(start: str | os.PathLike | None = None) -> Path:
    """Walk upward from ``start`` (default: cwd) until all marker paths exist.

    Falls back to ``CAML_ROOT`` env var if set, then to cwd if no marker
    directory is found (callers should validate before relying on it).
    """
    env_root = os.environ.get("CAML_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = Path(start or os.getcwd()).resolve()
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in _MARKERS):
            return candidate
    return current
