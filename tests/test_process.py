"""Regression tests for the 2026-09-15 `StaleProcessError` false-positive
fix in `caml.utils.process.run_subprocess()`.

Root cause: `communicate()`'s empty-reads sentinel (see `read_pipe()` in
`live_output_unix()`) can't tell "the process just exited, its pipes hit
real EOF" apart from "genuinely produced no output" -- both look identical
from the read loop's side. `run_subprocess()` used to trust a single
immediate `process.poll()` call to disambiguate, but a process that *just*
exited may not be reaped by the OS yet at that exact instant, so `poll()`
could read None for an already-finished process and raise a spurious
`StaleProcessError ... nan seconds`. Hit 3 times on a real VPS against very
fast commands (`uv venv`, `uv python install`); manual retries always
succeeded. Fixed with a short grace period (`process.wait(timeout=...)`)
before concluding the process is actually stale.

Uses real subprocesses (not mocks) with a fake `communicate_fn` that
mirrors `live_output_unix()`'s instant-empty-reads behavior, since that's
the actual shape of the race -- `run_subprocess()`'s own default
`communicate` (no custom `communicate_fn`) blocks for real process exit and
can't reproduce this race at all.
"""

import sys

import pytest

import caml.utils.process as process_mod
from caml.utils.process import StaleProcessError, run_subprocess


def _instant_communicate(process, input=None, timeout=None):
    """Mirrors `live_output_unix()` concluding communication (both pipes
    read as empty) without necessarily meaning the process has exited yet.
    """
    return "", ""


def test_run_subprocess_survives_late_reap_race():
    completed = run_subprocess(
        [sys.executable, "-c", "import time; time.sleep(0.05)"],
        communicate_fn=_instant_communicate,
    )
    assert completed.returncode == 0


def test_run_subprocess_genuine_hang_still_raises(monkeypatch):
    """A process that doesn't exit within the grace period is still
    correctly killed and reported as stale -- the fix must not turn this
    into a silent indefinite wait."""
    monkeypatch.setattr(process_mod, "_STALE_PROCESS_GRACE_SECS", 0.05)
    with pytest.raises(StaleProcessError):
        run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            communicate_fn=_instant_communicate,
        )
