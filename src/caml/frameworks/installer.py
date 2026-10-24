"""The shared framework installer.

This is the single piece of code that replaces all 11 hand-rolled
``setup.sh`` files from AMLB (see AMLB issues #64 "simplify install +
standardize venv usage" and #642 "defaults to improve framework integration
setup"). A ``framework.toml`` manifest only ever needs to declare *what*
differs between frameworks (version pin, Python range, system packages,
extra index URLs); this module is the only place that knows *how* to turn
that into a working isolated environment, via ``uv``.

Every step is idempotent and safe to re-run: `.setup/installed` (structured
JSON, not AMLB's flat-string marker) records exactly what's installed, and
if it already matches the manifest's pin + resolved Python version, install
is a no-op. On any mismatch the venv is blown away and rebuilt from
scratch rather than patched in place — cheap, and avoids the kind of
partial-upgrade drift AMLB's own `setup.sh` bug (missing `$` in an `-x`
test, always recreating the venv) stumbled into.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ..utils.process import run_cmd
from .manifest import FrameworkManifest, load_manifest

log = logging.getLogger(__name__)

# Preference order (newest first) of CPython minor versions `uv` is asked to
# resolve a framework's `[python].range` against. Extend this list forward
# as new CPython releases become relevant; there is no need to keep
# anything here that is older than the oldest framework's floor.
_CANDIDATE_PYTHONS = ["3.13", "3.12", "3.11", "3.10", "3.9"]

_SETUP_DIRNAME = ".setup"
_INSTALLED_MARKER = "installed"


class InstallError(RuntimeError):
    pass


def gpu_present() -> bool:
    """Whether this box should install GPU (CUDA) wheels — the install-time
    half of CAML's "GPU by default" policy (the run-time half is
    ``frameworks/shared/compute.py``, which both honour via ``CAML_COMPUTE``).

    torch isn't installed yet at install time, so unlike the run-time helper
    this can't ask ``torch.cuda`` — it probes the NVIDIA driver directly via
    ``nvidia-smi``. ``CAML_COMPUTE`` overrides detection: ``cpu`` forces CPU
    wheels even on a GPU box, ``gpu`` forces CUDA wheels even if ``nvidia-smi``
    can't be found (e.g. an unusual driver path), ``auto`` (default) detects.
    """
    pref = (os.environ.get("CAML_COMPUTE") or "auto").strip().lower()
    if pref == "cpu":
        return False
    if pref == "gpu":
        return True
    if pref not in ("auto", ""):
        log.warning("Unrecognized CAML_COMPUTE=%r; treating as 'auto'.", pref)
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        # `-L` lists GPUs, one per line ("GPU 0: NVIDIA RTX A4000 (UUID: ...)").
        result = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip().startswith("GPU ")


def _select_index_urls(manifest: FrameworkManifest) -> tuple[list[str], str]:
    """Pick the pip index URLs for this install and the compute-mode label.

    Returns ``(index_urls, mode)`` where ``mode`` is ``"gpu"``/``"cpu"`` (or
    ``"n/a"`` for a framework that declares no torch index at all). A framework
    only ever installs CUDA wheels when it *declares* a GPU index
    (``gpu_extra_index_urls``) **and** a GPU is actually present — so the
    CPU-bound roster is unaffected no matter what box it runs on.
    """
    if manifest.install.gpu_extra_index_urls and gpu_present():
        return manifest.install.gpu_extra_index_urls, "gpu"
    label = "cpu" if manifest.install.gpu_extra_index_urls else "n/a"
    return manifest.install.extra_index_urls, label


def resolve_python_version(range_spec: str) -> str:
    """Pick the newest CPython minor version satisfying ``range_spec``."""
    spec = SpecifierSet(range_spec)
    for candidate in _CANDIDATE_PYTHONS:
        if spec.contains(Version(f"{candidate}.0"), prereleases=True):
            return candidate
    raise InstallError(
        f"No candidate Python version in {_CANDIDATE_PYTHONS} satisfies range '{range_spec}'. "
        f"Add a newer/older candidate to _CANDIDATE_PYTHONS in installer.py."
    )


def _venv_dir(framework_dir: Path) -> Path:
    return framework_dir / "venv"


def _venv_python(framework_dir: Path) -> Path:
    return _venv_dir(framework_dir) / "bin" / "python"


def _marker_path(framework_dir: Path) -> Path:
    return framework_dir / _SETUP_DIRNAME / _INSTALLED_MARKER


def read_install_state(framework_dir: Path) -> dict | None:
    marker = _marker_path(framework_dir)
    if not marker.is_file():
        return None
    try:
        return json.loads(marker.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_install_state(framework_dir: Path, **fields) -> None:
    marker = _marker_path(framework_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(fields, indent=2, sort_keys=True) + "\n")


def _uv_version() -> str:
    out, _ = run_cmd("uv --version", _live_output_=False)
    return out.strip()


def _ensure_apt_packages(packages: list[str]) -> None:
    if not packages:
        return
    missing = []
    for pkg in packages:
        result = subprocess.run(
            ["dpkg", "-s", pkg], capture_output=True, text=True
        )
        if result.returncode != 0:
            missing.append(pkg)
    if not missing:
        log.info("apt packages already present: %s", ", ".join(packages))
        return
    log.info("Installing missing apt packages: %s", ", ".join(missing))
    run_cmd(
        f"sudo -n apt-get install -y {' '.join(missing)}",
        _live_output_=True,
        _env_={"DEBIAN_FRONTEND": "noninteractive"},
    )


def _strip_version_pin(spec: str) -> str:
    """Drop an exact ``==X.Y.Z`` pin from a pip requirement spec, used by
    the ``--latest`` escape hatch. Leaves extras (`pkg[extra]`) intact."""
    return re.sub(r"==[^\s;]+", "", spec)


def is_installed(framework_dir: Path, manifest: FrameworkManifest) -> bool:
    state = read_install_state(framework_dir)
    if state is None:
        return False
    return (
        state.get("pinned_version") == manifest.version_check.current_pin
        and _venv_python(framework_dir).is_file()
    )


def install(manifest: FrameworkManifest, *, latest: bool = False, force: bool = False) -> None:
    framework_dir = manifest.dir
    name = manifest.framework.name

    if not force and not latest and is_installed(framework_dir, manifest):
        log.info("%s already installed at pin %s, skipping.", name, manifest.version_check.current_pin)
        return

    log.info("Installing framework %s (pin=%s, latest=%s)", name, manifest.version_check.current_pin, latest)

    _ensure_apt_packages(manifest.install.system_packages.apt)

    python_version = resolve_python_version(manifest.python.range)
    run_cmd(f"uv python install {python_version}", _live_output_=True)

    venv_dir = _venv_dir(framework_dir)
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    run_cmd(f"uv venv {venv_dir} --python {python_version}", _live_output_=True)

    venv_python = _venv_python(framework_dir)
    shared_requirements = framework_dir.parent / "shared" / "requirements.txt"
    if shared_requirements.is_file():
        run_cmd(
            f"uv pip install --python {venv_python} -r {shared_requirements}",
            _live_output_=True,
        )

    packages = manifest.install.packages
    if latest:
        packages = [_strip_version_pin(p) for p in packages]
    # "GPU by default": a torch framework installs CUDA wheels when a GPU is
    # present on the box, CPU wheels otherwise (see _select_index_urls). The
    # CPU-bound roster declares no gpu_extra_index_urls, so this is a no-op for
    # them regardless of box.
    index_urls, compute_mode = _select_index_urls(manifest)
    if manifest.install.gpu_extra_index_urls:
        log.info(
            "%s: torch framework, installing %s wheels (index: %s)",
            name, compute_mode.upper(), ", ".join(index_urls) or "default PyPI",
        )
    if packages:
        # shlex.quote() is required, not cosmetic: run_cmd executes via a
        # shell, and version specifiers routinely contain shell-meaningful
        # characters (e.g. "setuptools<82") that get misinterpreted as
        # redirection/globbing otherwise -- found the hard way bringing up
        # TPOT (2026-07-29), the first framework needing a comparison
        # operator rather than an exact "==" pin.
        index_args = " ".join(
            f"--extra-index-url {shlex.quote(u)}" for u in index_urls
        )
        quoted_packages = " ".join(shlex.quote(p) for p in packages)
        run_cmd(
            f"uv pip install --python {venv_python} {index_args} {quoted_packages}",
            _live_output_=True,
        )

    if manifest.install.post_install_script:
        script_path = framework_dir / manifest.install.post_install_script
        run_cmd(f"{venv_python} {script_path}", _live_output_=True)

    installed_version = _detect_installed_version(venv_python, manifest.version_check.pypi_package)

    _write_install_state(
        framework_dir,
        framework=name,
        pinned_version=manifest.version_check.current_pin,
        installed_version=installed_version,
        python=python_version,
        uv_version=_uv_version(),
        installed_at=datetime.now(timezone.utc).isoformat(),
        latest_override=latest,
        compute=compute_mode,
    )
    log.info("Framework %s installed successfully (version=%s).", name, installed_version)


def _detect_installed_version(venv_python: Path, pypi_package: str) -> str:
    try:
        out, _ = run_cmd(
            f'{venv_python} -c "from importlib.metadata import version; print(version(\'{pypi_package}\'))"',
            _live_output_=False,
        )
        return out.strip()
    except Exception:
        log.warning("Could not detect installed version of %s via importlib.metadata", pypi_package)
        return "unknown"


def uninstall(manifest: FrameworkManifest) -> None:
    framework_dir = manifest.dir
    venv_dir = _venv_dir(framework_dir)
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    marker = _marker_path(framework_dir)
    if marker.exists():
        marker.unlink()
    log.info("Uninstalled framework %s.", manifest.framework.name)


def install_by_dir(framework_dir: Path, *, latest: bool = False, force: bool = False) -> None:
    manifest = load_manifest(framework_dir)
    install(manifest, latest=latest, force=force)
