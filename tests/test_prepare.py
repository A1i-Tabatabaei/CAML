"""Tests for caml.prepare (`caml prepare-data`): task-type inference, the
fold split, the files and benchmark YAML it writes, its input validation,
and an integration check that CAML's own benchmark + file-dataset loaders
read the result back as the right task (type, target, folds, row counts).
"""

from __future__ import annotations

import json
from copy import copy

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

from caml.prepare import PrepareError, detect_separator, infer_task_type, prepare_dataset, sanitize_name


def _toy_frame(n=60, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "customer_id": np.arange(n),
        "age": rng.integers(18, 80, n),
        "income": rng.normal(50_000, 12_000, n).round(2),
        "plan": rng.choice(["basic", "plus", "pro"], n),
        "churned": rng.choice([0, 1], n, p=[0.6, 0.4]),
    })


# --- task-type inference -----------------------------------------------------

@pytest.mark.parametrize("values, expected", [
    (["yes", "no", "yes"], "binary"),
    ([True, False, True], "binary"),
    ([0, 1, 1, 0], "binary"),
    (["a", "b", "c"], "multiclass"),
    ([1, 2, 3, 4, 2], "multiclass"),            # small set of integers -> class labels
    (list(range(50)), "regression"),            # many distinct integers -> regression
    ([0.5, 1.25, 3.0, 7.75], "regression"),
])
def test_infer_task_type(values, expected):
    assert infer_task_type(pd.Series(values))[0] == expected


def test_infer_task_type_rejects_constant_target():
    with pytest.raises(PrepareError, match="at least 2"):
        infer_task_type(pd.Series([1, 1, 1]))


def test_sanitize_name():
    assert sanitize_name("My Data (v2).final") == "My_Data_v2_final"
    with pytest.raises(PrepareError):
        sanitize_name("!!!")


# --- the split and the files ---------------------------------------------------

def test_kfold_split_writes_disjoint_stratified_folds_and_yaml(tmp_path):
    src = tmp_path / "churn.csv"
    _toy_frame().to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=3, drop=["customer_id"])

    assert res.task_type == "binary" and res.folds == 3 and res.rows == 60
    assert res.feature_columns == 3 and res.dropped_columns == ["customer_id"]
    d = tmp_path / "out" / "churn"
    tests = [pd.read_csv(d / f"churn_test_{k}.csv") for k in range(3)]
    trains = [pd.read_csv(d / f"churn_train_{k}.csv") for k in range(3)]
    assert sum(len(t) for t in tests) == 60                       # test folds partition the rows
    for train, test in zip(trains, tests):
        assert len(train) + len(test) == 60
        assert "customer_id" not in train.columns
        assert set(test["churned"]) == {0, 1}                     # stratified: both classes in every fold
    yaml_text = (d / "churn.yaml").read_text()
    assert "type: binary" in yaml_text and "folds: 3" in yaml_text and str(d / "churn_test_2.csv") in yaml_text
    prov = json.loads((d / "dataset.json").read_text())
    assert prov["seed"] == 42 and prov["split"] == "stratified k-fold" and len(prov["source_sha256"]) == 64


def test_split_is_reproducible_for_a_seed(tmp_path):
    src = tmp_path / "d.csv"
    _toy_frame().to_csv(src, index=False)
    prepare_dataset(src, "churned", tmp_path / "a", folds=2, seed=7)
    prepare_dataset(src, "churned", tmp_path / "b", folds=2, seed=7)
    a = (tmp_path / "a" / "d" / "d_test_0.csv").read_text()
    b = (tmp_path / "b" / "d" / "d_test_0.csv").read_text()
    assert a == b


def test_holdout_and_regression(tmp_path):
    df = _toy_frame(n=100)
    src = tmp_path / "income.parquet"
    df.to_parquet(src)
    res = prepare_dataset(src, "income", tmp_path / "out", folds=1, test_size=0.25)
    assert res.task_type == "regression" and res.class_counts is None
    test = pd.read_csv(tmp_path / "out" / "income" / "income_test_0.csv")
    assert len(test) == 25


def test_rows_with_missing_target_are_dropped_with_a_warning(tmp_path):
    df = _toy_frame().astype({"churned": "float"})
    df.loc[:4, "churned"] = np.nan
    src = tmp_path / "d.csv"
    df.to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=2)
    assert res.rows == 55 and res.dropped_rows == 5
    assert any("missing target" in w for w in res.warnings)


def test_id_column_warning(tmp_path):
    src = tmp_path / "d.csv"
    _toy_frame().to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=2)
    assert any("customer_id" in w for w in res.warnings)


# --- validation ----------------------------------------------------------------

def test_unknown_target_suggests_close_match(tmp_path):
    src = tmp_path / "d.csv"
    _toy_frame().to_csv(src, index=False)
    with pytest.raises(PrepareError, match="Did you mean: churned"):
        prepare_dataset(src, "churn", tmp_path / "out")


def test_rare_class_is_refused(tmp_path):
    df = _toy_frame()
    df.loc[0, "plan"] = "enterprise"                               # one row of a 4th class
    src = tmp_path / "d.csv"
    df.to_csv(src, index=False)
    with pytest.raises(PrepareError, match="enterprise"):
        prepare_dataset(src, "plan", tmp_path / "out", folds=5)


def test_explicit_type_is_checked(tmp_path):
    src = tmp_path / "d.csv"
    _toy_frame().to_csv(src, index=False)
    with pytest.raises(PrepareError, match="exactly 2"):
        prepare_dataset(src, "plan", tmp_path / "out", task_type="binary")
    with pytest.raises(PrepareError, match="numeric"):
        prepare_dataset(src, "plan", tmp_path / "out", task_type="regression")


def test_existing_output_needs_force(tmp_path):
    src = tmp_path / "d.csv"
    _toy_frame().to_csv(src, index=False)
    prepare_dataset(src, "churned", tmp_path / "out", folds=2)
    with pytest.raises(PrepareError, match="--force"):
        prepare_dataset(src, "churned", tmp_path / "out", folds=2)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=3, force=True)
    files = sorted(p.name for p in (tmp_path / "out" / "d").glob("d_t*_*.csv"))
    assert res.folds == 3 and len(files) == 6                     # no stale fold files left behind


def test_unsupported_file_type(tmp_path):
    src = tmp_path / "d.xlsx"
    src.write_bytes(b"not really excel")
    with pytest.raises(PrepareError, match="Unsupported"):
        prepare_dataset(src, "y", tmp_path / "out")


# --- CAML reads it back correctly ------------------------------------------------

def test_caml_loaders_read_the_prepared_benchmark(tmp_path):
    """The YAML resolves through resources.benchmark_definition() and every
    fold loads through the real FileLoader as a *binary* task, even though
    the target is a 0/1 integer column (which FileDataset would otherwise
    infer as regression)."""
    from caml import resources
    from caml.cli import _bootstrap_resources
    from caml.data import DatasetType
    from caml.datasets.file import FileLoader
    from caml.paths import find_repo_root

    src = tmp_path / "churn.csv"
    _toy_frame().to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=3, drop=["customer_id"])

    _bootstrap_resources(find_repo_root())
    res_ = resources.get()
    tasks, bench_name, _ = res_.benchmark_definition(res.benchmark_file, res_.constraint_definition("test"))
    task = next(t for t in tasks if t.name == "churn")
    assert bench_name == "churn" and task.folds == 3            # the task's folds win over the constraint's 2

    loader = FileLoader(cache_dir=str(tmp_path / "cache"))
    for fold in range(3):
        conf = copy(task.dataset)
        conf.name = task.name
        ds = loader.load(conf, fold=fold)
        assert ds.type == DatasetType.binary
        assert ds.target.name == "churned"
        assert len(ds.train.data) + len(ds.test.data) == 60
        assert list(ds.train.X.columns) == ["age", "income", "plan"]


def test_cli_prepare_data_and_help(tmp_path):
    from caml.cli import main

    src = tmp_path / "churn.csv"
    _toy_frame().to_csv(src, index=False)
    out = CliRunner().invoke(main, ["prepare-data", str(src), "--target", "churned", "--folds", "2",
                                    "--drop", "customer_id", "--out", str(tmp_path / "out")])
    assert out.exit_code == 0, out.output
    assert "Type      binary" in out.output and "caml sweep" in out.output
    bad = CliRunner().invoke(main, ["prepare-data", str(src), "--target", "nope", "--out", str(tmp_path / "o2")])
    assert bad.exit_code != 0 and "not found" in bad.output


def test_boolean_target_warning(tmp_path):
    df = _toy_frame()
    df["churned"] = df["churned"].astype(bool)
    src = tmp_path / "d.csv"
    df.to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=2)
    assert res.task_type == "binary" and any("True/False" in w for w in res.warnings)


# --- spreadsheet exports (Excel/Numbers, often from a Mac) ---------------------

def _export(path, text, encoding="utf-8", bom=False):
    data = text.encode(encoding)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


def _rows(n=40, sep=",", decimal="."):
    lines = [sep.join(["size", "weight", "label"])]
    for i in range(n):
        size, weight = f"{i % 7}{decimal}5", f"{10 + i}{decimal}25"
        lines.append(sep.join([size, weight, "yes" if i % 2 else "no"]))
    return "\r\n".join(lines) + "\r\n"


@pytest.mark.parametrize("header, expected", [
    ("a,b,c", ","), ("a;b;c", ";"), ("a\tb\tc", "\t"), ("a|b|c", "|"), ("onlyone", ","),
])
def test_detect_separator(tmp_path, header, expected):
    assert detect_separator(_export(tmp_path / "x.csv", header + "\n1\n")) == expected


def test_semicolon_csv_with_decimal_commas(tmp_path):
    src = _export(tmp_path / "eu.csv", _rows(sep=";", decimal=","), bom=True)
    res = prepare_dataset(src, "label", tmp_path / "out", name="eu", folds=2)
    assert res.task_type == "binary" and res.feature_columns == 2
    assert any("decimal commas" in w for w in res.warnings)
    train = pd.read_csv(tmp_path / "out" / "eu" / "eu_train_0.csv")
    assert pd.api.types.is_float_dtype(train["size"]) and pd.api.types.is_float_dtype(train["weight"])


def test_semicolon_csv_with_decimal_points(tmp_path):
    src = _export(tmp_path / "semi.csv", _rows(sep=";"))
    res = prepare_dataset(src, "label", tmp_path / "out", name="semi", folds=2)
    assert any("semicolon-separated" in w for w in res.warnings)
    assert not any("decimal commas" in w for w in res.warnings)


def test_bom_and_crlf_need_no_note(tmp_path):
    src = _export(tmp_path / "excel.csv", _rows(), bom=True)
    res = prepare_dataset(src, "label", tmp_path / "out", name="excel", folds=2)
    assert res.target == "label" and not res.warnings


def test_non_utf8_csv_gets_a_clear_error(tmp_path):
    src = _export(tmp_path / "legacy.csv", _rows().replace("label", "Ergebnis_\u00e4"), encoding="mac_roman")
    with pytest.raises(PrepareError, match="isn't UTF-8.*iconv"):
        prepare_dataset(src, "Ergebnis_\u00e4", tmp_path / "out", name="legacy", folds=2)


# --- columns by number, --keep, --metric (1.2.0) ---------------------------------

def test_columns_by_number_keep_and_metric(tmp_path):
    src = tmp_path / "churn.csv"
    df = _toy_frame().rename(columns={"plan": "Plan Type"})
    df.to_csv(src, index=False)
    # Column 4 is "Plan Type": a name that can't cross an ssh command line unquoted.
    res = prepare_dataset(src, "5", tmp_path / "out", keep=["2", "4"], metrics=["balacc", "AUC"])
    assert res.target == "churned"
    assert res.feature_columns == 2 and set(res.dropped_columns) == {"customer_id", "income"}
    assert res.metrics == ["balacc", "auc"]
    yaml_text = (tmp_path / "out" / "churn" / "churn.yaml").read_text()
    assert "  metric: [balacc, auc]" in yaml_text
    train = pd.read_csv(tmp_path / "out" / "churn" / "churn_train_0.csv")
    assert list(train.columns) == ["age", "Plan Type", "churned"]
    assert json.loads((tmp_path / "out" / "churn" / "dataset.json").read_text())["metrics"] == ["balacc", "auc"]


def test_metric_must_fit_the_task_and_drop_excludes_keep(tmp_path):
    src = tmp_path / "churn.csv"
    _toy_frame().to_csv(src, index=False)
    with pytest.raises(PrepareError, match="don't apply to a binary task"):
        prepare_dataset(src, "churned", tmp_path / "a", metrics=["rmse"])
    with pytest.raises(PrepareError, match="not both"):
        prepare_dataset(src, "churned", tmp_path / "b", drop=["age"], keep=["plan"])
    with pytest.raises(PrepareError, match="describe-data"):
        prepare_dataset(src, "churned", tmp_path / "c", drop=["9"])


def test_caml_reads_the_metric_back(tmp_path):
    from caml import resources
    from caml.cli import _bootstrap_resources
    from caml.paths import find_repo_root

    src = tmp_path / "churn.csv"
    _toy_frame().to_csv(src, index=False)
    res = prepare_dataset(src, "churned", tmp_path / "out", folds=2, drop=["1"], metrics=["balacc", "auc"])
    _bootstrap_resources(find_repo_root())
    res_ = resources.get()
    tasks, _, _ = res_.benchmark_definition(res.benchmark_file, res_.constraint_definition("test"))
    task = next(t for t in tasks if t.name == "churn")
    assert list(task.metric) == ["balacc", "auc"]
