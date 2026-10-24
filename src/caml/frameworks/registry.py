"""Framework discovery.

Replaces AMLB's ``resources/frameworks.yaml`` central catalogue with
directory-based auto-discovery of ``frameworks/<Name>/framework.toml`` —
eliminates the dual-source-of-truth AMLB has today (a central YAML *and*
per-framework directories that must stay in sync).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .manifest import FrameworkManifest, load_manifest

# Directories under frameworks/ that are infrastructure, not a framework.
_NON_FRAMEWORK_DIRS = {"shared"}


@dataclass
class FrameworkDefinition:
    """Adapter exposing the subset of the old AMLB ``Framework`` dataclass
    shape that ``benchmark.py``/``BenchmarkTask`` still consume, backed by a
    ``FrameworkManifest`` instead of a ``resources/frameworks.yaml`` entry."""

    name: str
    module: str
    version: str
    manifest: FrameworkManifest
    params: dict = field(default_factory=dict)
    # unused in CAML's install model (installer.py handles setup directly),
    # kept only so benchmark.py's existing setup()/run() plumbing doesn't
    # need special-casing for the "no legacy setup script" case.
    setup_env: dict = field(default_factory=dict)
    setup_args: list = field(default_factory=list)
    setup_script: str | None = None
    setup_cmd: str | None = None


class FrameworkNotFoundError(ValueError):
    pass


def discover_frameworks(frameworks_root: Path) -> dict[str, FrameworkDefinition]:
    """Scan ``frameworks_root`` for ``<Name>/framework.toml`` manifests."""
    definitions: dict[str, FrameworkDefinition] = {}
    if not frameworks_root.is_dir():
        return definitions
    for entry in sorted(frameworks_root.iterdir()):
        if not entry.is_dir() or entry.name in _NON_FRAMEWORK_DIRS or entry.name.startswith("."):
            continue
        manifest_path = entry / "framework.toml"
        if not manifest_path.exists():
            continue
        manifest = load_manifest(entry)
        definitions[manifest.framework.name.lower()] = FrameworkDefinition(
            name=manifest.framework.name,
            module=f"frameworks.{entry.name}",
            version=manifest.version_check.current_pin,
            manifest=manifest,
        )
    return definitions


def get_framework(frameworks_root: Path, name: str) -> FrameworkDefinition:
    definitions = discover_frameworks(frameworks_root)
    key = name.lower()
    if key not in definitions:
        available = ", ".join(sorted(d.name for d in definitions.values())) or "(none found)"
        raise FrameworkNotFoundError(
            f"Unknown framework '{name}'. Available: {available}"
        )
    return definitions[key]


def load_framework_definition(name: str, frameworks_root: Path) -> FrameworkDefinition:
    """Drop-in-shaped replacement for AMLB's
    ``amlb.frameworks.definitions.load_framework_definition``."""
    return get_framework(frameworks_root, name)
