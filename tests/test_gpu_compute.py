"""Unit tests for CAML's Phase-8 GPU support: the run-time device resolver
(``frameworks/shared/compute.py``) and the install-time index selection
(``caml.frameworks.installer``). Both honour the same ``CAML_COMPUTE`` knob;
these tests pin the override semantics and the "no GPU wheel path => never
touched" guarantee for the CPU-bound roster, without needing a real GPU.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from frameworks.shared import compute  # noqa: E402
from caml.frameworks import installer  # noqa: E402
from caml.frameworks.manifest import load_manifest  # noqa: E402

FRAMEWORKS_ROOT = REPO_ROOT / "frameworks"


# --------------------------------------------------------------------------
# run-time: frameworks/shared/compute.py
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "env,cuda,expected",
    [
        ("cpu", True, False),    # force-cpu wins even with a GPU present
        ("cpu", False, False),
        ("gpu", True, True),     # force-gpu honoured when a GPU is present
        ("gpu", False, False),   # ...but falls back to CPU, never crashes
        ("auto", True, True),    # auto uses the GPU when present
        ("auto", False, False),  # auto falls back cleanly
        (None, True, True),      # unset == auto
        (None, False, False),
        ("nonsense", True, True),  # unrecognized == auto (with a warning)
    ],
)
def test_use_gpu_honours_override(monkeypatch, env, cuda, expected):
    if env is None:
        monkeypatch.delenv("CAML_COMPUTE", raising=False)
    else:
        monkeypatch.setenv("CAML_COMPUTE", env)
    monkeypatch.setattr(compute, "cuda_available", lambda: cuda)
    assert compute.use_gpu() is expected
    assert compute.torch_device() == ("cuda" if expected else "cpu")


def test_cuda_available_is_false_without_torch(monkeypatch):
    # The orchestrator venv has no torch; the helper must degrade to False,
    # not raise. (Also the real-world state on a framework venv with a broken
    # torch/driver combo.)
    monkeypatch.delenv("CAML_COMPUTE", raising=False)
    assert compute.cuda_available() is False
    assert compute.use_gpu() is False


# --------------------------------------------------------------------------
# install-time: caml.frameworks.installer
# --------------------------------------------------------------------------

def test_gpu_present_override(monkeypatch):
    monkeypatch.setenv("CAML_COMPUTE", "cpu")
    assert installer.gpu_present() is False
    monkeypatch.setenv("CAML_COMPUTE", "gpu")
    assert installer.gpu_present() is True


def test_gpu_present_auto_without_driver(monkeypatch):
    # auto + no nvidia-smi on PATH => CPU, deterministically.
    monkeypatch.setenv("CAML_COMPUTE", "auto")
    monkeypatch.setattr(installer.shutil, "which", lambda _: None)
    assert installer.gpu_present() is False


def test_select_index_urls_torch_framework(monkeypatch):
    # TabPFN declares both a CPU and a GPU index -> selection follows gpu_present.
    manifest = load_manifest(FRAMEWORKS_ROOT / "TabPFN")
    assert manifest.install.gpu_extra_index_urls, "TabPFN should declare a GPU index"

    monkeypatch.setattr(installer, "gpu_present", lambda: True)
    urls, mode = installer._select_index_urls(manifest)
    assert mode == "gpu"
    assert urls == manifest.install.gpu_extra_index_urls

    monkeypatch.setattr(installer, "gpu_present", lambda: False)
    urls, mode = installer._select_index_urls(manifest)
    assert mode == "cpu"
    assert urls == manifest.install.extra_index_urls


def test_select_index_urls_cpu_bound_framework(monkeypatch):
    # A CPU-bound framework declares no GPU index: selection is a no-op ("n/a")
    # regardless of whether the box has a GPU -- the roster is never forced onto
    # CUDA wheels it can't use.
    manifest = load_manifest(FRAMEWORKS_ROOT / "FLAML")
    assert not manifest.install.gpu_extra_index_urls

    for present in (True, False):
        monkeypatch.setattr(installer, "gpu_present", lambda: present)
        urls, mode = installer._select_index_urls(manifest)
        assert mode == "n/a"
        assert urls == manifest.install.extra_index_urls
