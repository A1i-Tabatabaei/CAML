"""scripts/lib_package.sh: the archive provision_vps.sh and sync_vps.sh push.

Runs the real shell function against a throwaway git repo. CI also runs this
file on macOS, where it uses the stock /bin/bash (3.2), BSD mktemp and
bsdtar: until 2026-10-24 the helper used GNU-only `mktemp --suffix` and
`tar --transform`, so both scripts failed on a Mac at their first step.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "scripts" / "lib_package.sh"
# The stock shell on a Mac is /bin/bash 3.2; test with what users have.
BASH = "/bin/bash" if sys.platform == "darwin" else (shutil.which("bash") or "/bin/bash")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text("print('a')\n")
    (repo / "README.md").write_text("hello\n")
    (repo / ".gitignore").write_text("*.local.md\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    # Never packaged from HEAD; the worktree mode picks up only the untracked one.
    (repo / "untracked.txt").write_text("new\n")
    (repo / "secret.local.md").write_text("never packaged\n")
    return repo


def _package(repo: Path, out: Path, include_worktree: str, env: dict[str, str] | None = None) -> None:
    script = f'set -euo pipefail; source "{LIB}"; caml_package_archive "{out}" {include_worktree}'
    subprocess.run([BASH, "-c", script], cwd=repo, check=True, capture_output=True, text=True, env=env)


def _members(archive: Path) -> dict[str, tarfile.TarInfo]:
    with tarfile.open(archive) as tar:
        return {m.name.rstrip("/"): m for m in tar.getmembers()}


def _revision(archive: Path) -> dict[str, str]:
    with tarfile.open(archive) as tar:
        text = tar.extractfile("CAML/REVISION").read().decode()
    return dict(line.split("=", 1) for line in text.splitlines())


def test_head_archive_has_prefix_and_revision(repo: Path, tmp_path: Path):
    out = tmp_path / "head.tar.gz"
    _package(repo, out, "0")
    names = set(_members(out))
    assert {"CAML/src/a.py", "CAML/README.md", "CAML/.gitignore", "CAML/REVISION"} <= names
    assert "CAML/untracked.txt" not in names
    assert all(n == "CAML" or n.startswith("CAML/") for n in names)
    assert not any(Path(n).name.startswith("._") for n in names)  # no macOS AppleDouble files
    rev = _revision(out)
    assert rev == {"commit": _git(repo, "rev-parse", "HEAD"), "branch": "main", "dirty": "0"}


def test_worktree_archive_adds_untracked_but_not_ignored(repo: Path, tmp_path: Path):
    out = tmp_path / "worktree.tar.gz"
    _package(repo, out, "1")
    names = set(_members(out))
    assert {"CAML/src/a.py", "CAML/untracked.txt", "CAML/REVISION"} <= names
    assert "CAML/secret.local.md" not in names
    assert _revision(out)["dirty"] == "1"


def test_archive_extracts_where_setup_workspace_expects(repo: Path, tmp_path: Path):
    # setup_workspace.sh and sync_vps.sh both run `tar xzf <archive>` in the
    # workspace directory and expect a CAML/ folder.
    out = tmp_path / "head.tar.gz"
    _package(repo, out, "0")
    dest = tmp_path / "workspace"
    dest.mkdir()
    subprocess.run(["tar", "xzf", str(out)], cwd=dest, check=True)
    assert (dest / "CAML" / "src" / "a.py").read_text() == "print('a')\n"
    assert (dest / "CAML" / "REVISION").is_file()


def test_no_gnu_only_options(repo: Path, tmp_path: Path):
    """Catch a macOS regression on Linux too: shims that refuse the GNU-only
    options BSD mktemp and bsdtar don't have, the way a Mac does."""
    shims = tmp_path / "bsd-shims"
    shims.mkdir()
    for tool, banned in (("mktemp", "--suffix"), ("tar", "--transform")):
        real = shutil.which(tool)
        shim = shims / tool
        shim.write_text(
            "#!/bin/sh\n"
            f'for a in "$@"; do case "$a" in {banned}*) echo "{tool}: illegal option $a" >&2; exit 64;; esac; done\n'
            f'exec "{real}" "$@"\n'
        )
        shim.chmod(0o755)
    env = {**os.environ, "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}"}
    for mode in ("0", "1"):
        out = tmp_path / f"bsd-{mode}.tar.gz"
        _package(repo, out, mode, env=env)
        assert "CAML/REVISION" in _members(out)


@pytest.mark.parametrize("script", ["provision_vps.sh", "sync_vps.sh", "lib_package.sh"])
def test_operator_scripts_avoid_gnu_only_options(script: str):
    """These three run on the user's machine, which may be a Mac."""
    code = [line for line in (LIB.parent / script).read_text().splitlines() if not line.lstrip().startswith("#")]
    for option in ("--suffix", "--transform", "sed -i ", "readlink -f", "date -d", "stat -c"):
        assert not any(option in line for line in code), f"{script} uses GNU-only {option!r}"
