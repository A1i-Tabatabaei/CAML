"""Unit tests for the caller.py/callee.py IPC boundary (see that module's
docstring: run_in_venv() must stay agnostic to how the venv was created,
since it's the mechanism that lets `uv venv` be a drop-in replacement for
AMLB's stdlib `venv`.)
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from frameworks.shared.caller import (  # noqa: E402
    STORAGE_ENV_VARS,
    retained_env,
    venv_bin,
    venv_python_exec,
)


def test_venv_paths_are_agnostic_to_creation_method(tmp_path):
    framework_dir = tmp_path / "SomeFramework"
    venv_dir = framework_dir / "venv" / "bin"
    venv_dir.mkdir(parents=True)
    (venv_dir / "python").touch()

    assert venv_bin(str(framework_dir)) == str(venv_dir)
    assert venv_python_exec(str(framework_dir)) == f"{venv_dir}/python -W ignore"


def test_storage_env_vars_always_cross_the_subprocess_boundary():
    # A redirected HOME/XDG (scripts/sync_local.sh) must reach every
    # framework, not just the ones that list HOME themselves -- otherwise
    # their caches silently land on the system disk.
    environ = {
        "HOME": "/drive/home",
        "XDG_CACHE_HOME": "/drive/cache",
        "TMPDIR": "/drive/tmp",
        "TABPFN_TOKEN": "secret",
        "UNRELATED": "x",
    }
    env = retained_env(["TMP", "TEMP", "TMPDIR"], environ=environ)
    assert env == {
        "HOME": "/drive/home",
        "XDG_CACHE_HOME": "/drive/cache",
        "TMPDIR": "/drive/tmp",
    }
    assert {"HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"} <= set(STORAGE_ENV_VARS)


def test_retained_env_adds_framework_specific_vars_and_skips_unset():
    environ = {"HOME": "/h", "TABPFN_TOKEN": "t"}
    assert retained_env(["TABPFN_TOKEN", "TABPFN_MODEL_CACHE_DIR"], environ=environ) == {
        "HOME": "/h",
        "TABPFN_TOKEN": "t",
    }
    assert retained_env(None, environ={}) == {}
