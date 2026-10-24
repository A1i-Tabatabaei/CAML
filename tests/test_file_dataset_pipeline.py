"""End-to-end check of the "benchmark your own data" path, with no AutoML
framework installed: `caml prepare-data` -> `caml run` -> results.csv ->
`caml leaderboard`, all as real `caml` subprocesses.

It builds a throwaway CAML root (src/, frameworks/shared and the resource
files linked or copied from this repo) holding one extra framework,
`SklearnBaseline`, whose exec.py fits scikit-learn's
HistGradientBoosting. That runs through the real orchestrator path: the
file-dataset loader, run_in_venv's subprocess boundary and serialization
(with this test venv's own interpreter standing in for a framework venv),
scoring, and the results.csv append. The only thing not exercised is a real
AutoML package, which needs `caml install` on a VPS.

Added 2026-10-24, after the local-CSV path was found broken under pandas 3
(`dtypes[i]` positional lookup in caml/datasets/file.py) despite being
documented as supported: it had never been run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CAML_EXE = Path(sys.executable).with_name("caml")

MANIFEST = """
[framework]
name = "SklearnBaseline"
tier = 1
project_url = "https://scikit-learn.org"
license = "BSD-3-Clause"

[python]
range = ">=3.11"

[install]
packages = []

[version_check]
pypi_package = "scikit-learn"
current_pin = "test"
"""

INIT = """
import sys


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(X=dataset.train.X, y=dataset.train.y),
        test=dict(X=dataset.test.X, y=dataset.test.y),
        problem_type=dataset.type.name,
    )
    # This test venv's interpreter stands in for frameworks/<name>/venv/bin/python.
    return run_in_venv(__file__, "exec.py", input_data=data, dataset=dataset, config=config,
                       python_exec=sys.executable)
"""

EXEC = """
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from frameworks.shared.callee import call_run, result


def run(dataset, config):
    X_train, y_train = dataset.train.X, dataset.train.y.squeeze()
    X_test, y_test = dataset.test.X, dataset.test.y.squeeze()
    classification = config.type == "classification"
    model = (HistGradientBoostingClassifier if classification else HistGradientBoostingRegressor)(
        categorical_features="from_dtype", random_state=0)
    model.fit(X_train, y_train)
    return result(
        output_file=config.output_predictions_file,
        predictions=model.predict(X_test),
        probabilities=model.predict_proba(X_test) if classification else None,
        probabilities_labels=model.classes_.tolist() if classification else None,
        truth=y_test,
        models_count=1,
    )


if __name__ == "__main__":
    call_run(run)
"""


BROKEN_EXEC = """
from frameworks.shared.callee import call_run


def run(dataset, config):
    raise ValueError("deliberate failure from the Broken test framework")


if __name__ == "__main__":
    call_run(run)
"""


def _add_framework(fw_dir: Path, name: str, exec_py: str) -> None:
    d = fw_dir / name
    d.mkdir()
    (d / "framework.toml").write_text(MANIFEST.replace('name = "SklearnBaseline"', f'name = "{name}"'))
    (d / "__init__.py").write_text(INIT)
    (d / "exec.py").write_text(exec_py)
    # What `caml install` would leave behind (is_installed checks both).
    (d / ".setup").mkdir()
    (d / ".setup" / "installed").write_text(json.dumps({"pinned_version": "test", "installed_version": "test"}))
    (d / "venv" / "bin").mkdir(parents=True)
    (d / "venv" / "bin" / "python").write_text("")


@pytest.fixture()
def caml_root(tmp_path):
    root = tmp_path / "caml-root"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'caml-test-root'\n")
    (root / "src").symlink_to(REPO_ROOT / "src")
    shutil.copytree(REPO_ROOT / "resources", root / "resources")
    fw = root / "frameworks"
    fw.mkdir()
    (fw / "__init__.py").write_text("")
    (fw / "shared").symlink_to(REPO_ROOT / "frameworks" / "shared")
    _add_framework(fw, "SklearnBaseline", EXEC)
    _add_framework(fw, "Broken", BROKEN_EXEC)
    return root


def _caml(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CAML_ROOT": str(root)}
    return subprocess.run([str(CAML_EXE), *args], cwd=root, env=env, capture_output=True, text=True, timeout=600)


@pytest.mark.skipif(not CAML_EXE.exists(), reason="needs the orchestrator venv's `caml` console script")
@pytest.mark.parametrize("kind", ["binary", "multiclass", "regression"])
def test_prepare_run_leaderboard_on_a_local_csv(caml_root, tmp_path, kind):
    rng = np.random.default_rng(1)
    n = 120
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    df = pd.DataFrame({"x1": x1, "x2": x2, "color": rng.choice(["red", "green", "blue"], n)})
    if kind == "binary":
        df["label"] = (x1 + 0.3 * rng.normal(size=n) > 0).astype(int)        # 0/1 ints: must stay binary
    elif kind == "multiclass":
        df["label"] = np.where(x1 > 0.5, "high", np.where(x1 < -0.5, "low", "mid"))
    else:
        df["label"] = 3 * x1 - x2 + rng.normal(scale=0.1, size=n)
    src = tmp_path / f"{kind}.csv"
    df.to_csv(src, index=False)

    prep = _caml(caml_root, "prepare-data", str(src), "--target", "label", "--folds", "2")
    assert prep.returncode == 0, prep.stdout + prep.stderr
    assert f"Type      {kind}" in prep.stdout
    bench = caml_root / "input" / "datasets" / kind / f"{kind}.yaml"
    assert bench.is_file()

    run = _caml(caml_root, "run", "SklearnBaseline", "--benchmark", str(bench), "--constraint", "test")
    assert run.returncode == 0, (run.stdout + run.stderr)[-4000:]

    results = pd.read_csv(caml_root / "output" / "results.csv")
    assert len(results) == 2 and set(results["fold"]) == {0, 1}
    assert results["result"].notna().all(), results[["fold", "result", "info"]].to_string()
    assert set(results["type"]) == {kind}
    expected_metric = {"binary": "auc", "multiclass": "neg_logloss", "regression": "neg_rmse"}[kind]
    assert set(results["metric"]) == {expected_metric}
    if kind == "binary":
        assert (results["auc"] > 0.8).all()                                   # a real model, not noise
    if kind == "regression":
        assert (results["r2"] > 0.5).all()

    board = _caml(caml_root, "leaderboard", "--benchmark", str(bench))
    assert board.returncode == 0, board.stdout + board.stderr
    assert "SklearnBaseline" in board.stdout and "2/2" in board.stdout


@pytest.mark.skipif(not CAML_EXE.exists(), reason="needs the orchestrator venv's `caml` console script")
def test_keep_going_records_failed_jobs_and_leaderboard_reports_them(caml_root, tmp_path):
    """A framework that raises on every fold: with --keep-going each fold is
    recorded as an error row (empty result, the error in `info`) instead of
    aborting with nothing written, and the leaderboard ranks the working
    framework while listing the broken one as failed."""
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"x": rng.normal(size=80), "y": rng.choice(["a", "b"], 80)})
    src = tmp_path / "tiny.csv"
    df.to_csv(src, index=False)
    assert _caml(caml_root, "prepare-data", str(src), "--target", "y", "--folds", "2").returncode == 0
    bench = str(caml_root / "input" / "datasets" / "tiny" / "tiny.yaml")

    broken = _caml(caml_root, "run", "Broken", "--benchmark", bench, "--constraint", "test", "--keep-going")
    assert broken.returncode == 0, (broken.stdout + broken.stderr)[-4000:]
    ok = _caml(caml_root, "run", "SklearnBaseline", "--benchmark", bench, "--constraint", "test")
    assert ok.returncode == 0, (ok.stdout + ok.stderr)[-4000:]

    results = pd.read_csv(caml_root / "output" / "results.csv")
    failed = results[results["framework"] == "Broken"]
    assert len(failed) == 2 and failed["result"].isna().all()
    assert failed["info"].str.contains("deliberate failure").all()

    board = _caml(caml_root, "leaderboard", "--benchmark", bench)
    assert board.returncode == 0, board.stdout + board.stderr
    lines = board.stdout.splitlines()
    assert any(line.startswith("1 ") and "SklearnBaseline" in line for line in lines)
    assert any("Broken" in line and "0/2" in line for line in lines)
    assert "deliberate failure" in board.stdout
