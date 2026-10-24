from pathlib import Path

import pytest

from caml.frameworks.manifest import ManifestError, load_manifest
from caml.frameworks.registry import discover_frameworks

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORKS_ROOT = REPO_ROOT / "frameworks"


def _framework_dirs():
    return [
        d for d in sorted(FRAMEWORKS_ROOT.iterdir())
        if d.is_dir() and d.name != "shared" and (d / "framework.toml").exists()
    ]


@pytest.mark.parametrize("framework_dir", _framework_dirs(), ids=lambda d: d.name)
def test_manifest_is_valid(framework_dir):
    manifest = load_manifest(framework_dir)
    assert manifest.framework.name
    assert manifest.version_check.current_pin
    assert manifest.install.packages


def test_discover_frameworks_finds_reference_implementations():
    definitions = discover_frameworks(FRAMEWORKS_ROOT)
    assert "flaml" in definitions
    assert "mljarsupervised" in definitions
    assert definitions["flaml"].module == "frameworks.FLAML"


def test_missing_manifest_raises():
    with pytest.raises(ManifestError):
        load_manifest(FRAMEWORKS_ROOT / "shared")
