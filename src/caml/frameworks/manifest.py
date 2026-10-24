"""Declarative per-framework manifest (``framework.toml``).

Replaces AMLB's hand-rolled per-framework ``setup.sh`` + central
``resources/frameworks.yaml`` entry (see AMLB issues #64, #642) with one
manifest per framework, loaded with stdlib ``tomllib`` and validated with
pydantic so malformed manifests fail loudly with a clear field-level error
instead of AMLB's silent/late failures from a malformed YAML entry.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class SystemPackages(BaseModel):
    apt: list[str] = Field(default_factory=list)


class InstallSpec(BaseModel):
    packages: list[str] = Field(default_factory=list)
    # Package index(es) used when installing on a CPU-only box (the default).
    # For the torch frameworks this pins the CPU-only wheel
    # (download.pytorch.org/whl/cpu) so a CPU box never pulls multi-GB CUDA
    # builds it can't use.
    extra_index_urls: list[str] = Field(default_factory=list)
    # Package index(es) used *instead* when a usable GPU is detected on the box
    # (or CAML_COMPUTE=gpu). For the torch frameworks this points at the CUDA
    # wheel index (download.pytorch.org/whl/cuXXX). Empty => no GPU-specific
    # index, so `extra_index_urls` is used regardless of GPU presence (correct
    # for every non-torch framework). See installer.py::_select_index_urls and
    # docs/operations/gpu.md.
    gpu_extra_index_urls: list[str] = Field(default_factory=list)
    post_install_script: str = ""
    system_packages: SystemPackages = Field(default_factory=SystemPackages)


class PythonSpec(BaseModel):
    range: str


class VersionCheck(BaseModel):
    pypi_package: str
    current_pin: str


class ExecSpec(BaseModel):
    entrypoint: str = "exec.py"


class FrameworkInfo(BaseModel):
    name: str
    tier: int
    project_url: str
    license: str


class NotesSpec(BaseModel):
    last_verified: str = ""
    gotchas: str = ""


class FrameworkManifest(BaseModel):
    framework: FrameworkInfo
    python: PythonSpec
    install: InstallSpec
    version_check: VersionCheck
    exec: ExecSpec = Field(default_factory=ExecSpec)
    notes: NotesSpec = Field(default_factory=NotesSpec)

    # populated by the loader, not present in the TOML file itself
    dir: Path = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


class ManifestError(ValueError):
    """Raised when a framework.toml is missing or fails schema validation."""


def load_manifest(framework_dir: Path) -> FrameworkManifest:
    manifest_path = framework_dir / "framework.toml"
    if not manifest_path.is_file():
        raise ManifestError(f"No framework.toml found in {framework_dir}")
    try:
        raw = tomllib.loads(manifest_path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"{manifest_path}: invalid TOML: {e}") from e
    try:
        manifest = FrameworkManifest.model_validate(raw)
    except ValidationError as e:
        raise ManifestError(f"{manifest_path}: schema validation failed:\n{e}") from e
    manifest.dir = framework_dir
    return manifest
