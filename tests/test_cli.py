"""CLI behaviour not covered elsewhere: `caml install --all` keeps going past
a failed install, and sweeps on a YAML path get a readable default name."""

from __future__ import annotations

from click.testing import CliRunner

from caml import sweep
from caml.cli import main


def test_install_all_continues_past_a_failure_and_exits_nonzero(monkeypatch):
    from caml.cli import installer_mod

    attempted = []

    def fake_install(manifest, latest=False, force=False):
        attempted.append(manifest.framework.name)
        if manifest.framework.name == "FLAML":
            raise RuntimeError("uv pip install failed\nlong traceback here")

    monkeypatch.setattr(installer_mod, "install", fake_install)
    res = CliRunner().invoke(main, ["install", "--all"])
    assert res.exit_code == 1
    assert "FLAML" in attempted and len(attempted) > 2           # kept going after FLAML
    assert "FLAML: uv pip install failed" in res.output and "long traceback" not in res.output


def test_install_single_framework_still_raises(monkeypatch):
    from caml.cli import installer_mod

    def boom(manifest, latest=False, force=False):
        raise RuntimeError("nope")

    monkeypatch.setattr(installer_mod, "install", boom)
    res = CliRunner().invoke(main, ["install", "FLAML"])
    assert res.exit_code != 0 and isinstance(res.exception, RuntimeError)


def test_default_sweep_name_uses_yaml_stem():
    assert sweep.default_sweep_name("input/datasets/churn/churn.yaml", "quick") == "churn-quick"
    assert sweep.default_sweep_name("/abs/x/My Data.yml", "1h8c") == "My-Data-1h8c"
    assert sweep.default_sweep_name("openml/s/271", "1h8c") == "openml-s-271-1h8c"
