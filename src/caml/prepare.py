"""Turn one tabular data file into a CAML benchmark (``caml prepare-data``).

CAML's file-dataset loader (``caml.datasets.file``, ported from AMLB) needs
pre-split train/test files, one pair per fold, plus a benchmark definition
YAML pointing at them. Doing that by hand is where people go wrong:
leakage from splitting after preprocessing, unstratified folds, a 0/1
integer target silently treated as regression (``FileDataset.type`` infers
"regression" for any numeric target unless ``type`` is set), relative paths
that break once a sweep's subprocess runs from another directory. This
module does it once, correctly, and records what it did.

Output layout (``out_dir/<name>/``)::

    <name>.yaml              benchmark definition: pass it to --benchmark
    <name>_train_<k>.csv     fold k training split
    <name>_test_<k>.csv      fold k held-out split
    dataset.json             provenance: source sha256, seed, type, counts

Pure pandas/scikit-learn, no ``caml.*`` runtime imports, so it's directly
unit-testable (same pattern as ``stats.py``). The CLI glue is in ``cli.py``.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split

TASK_TYPES = ("binary", "multiclass", "regression")
SUPPORTED_SUFFIXES = (".csv", ".tsv", ".parquet", ".pq")
# An integer-valued numeric target with at most this many distinct values is
# treated as class labels (with a warning), above it as a regression target.
MAX_INT_CLASSES = 10


class PrepareError(ValueError):
    """The input can't be turned into a valid benchmark (bad target, too few rows, ...)."""


@dataclass
class PrepareResult:
    name: str
    task_type: str
    type_reason: str
    target: str
    folds: int
    rows: int
    feature_columns: int
    benchmark_file: str
    dataset_dir: str
    dropped_rows: int = 0
    dropped_columns: list[str] = field(default_factory=list)
    class_counts: dict[str, int] | None = None
    warnings: list[str] = field(default_factory=list)


def sanitize_name(name: str) -> str:
    """A task name that is safe in file names, job names and results.csv."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-")
    if not cleaned:
        raise PrepareError(f"Can't derive a usable dataset name from {name!r}; pass --name.")
    return cleaned


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    raise PrepareError(
        f"Unsupported file type {suffix!r}. Use one of: {', '.join(SUPPORTED_SUFFIXES)} "
        "(export spreadsheets to CSV first)."
    )


def infer_task_type(y: pd.Series) -> tuple[str, str]:
    """Return ``(task_type, reason)`` for a target column with missing values removed."""
    n_unique = int(y.nunique())
    if n_unique < 2:
        raise PrepareError(f"Target has {n_unique} distinct value(s); need at least 2.")
    if not pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y):
        kind = "binary" if n_unique == 2 else "multiclass"
        return kind, f"non-numeric target with {n_unique} distinct values"
    if n_unique == 2:
        return "binary", "numeric target with exactly 2 distinct values"
    values = y.to_numpy(dtype=float)
    if np.all(np.isfinite(values)) and np.all(values == np.round(values)) and n_unique <= MAX_INT_CLASSES:
        return "multiclass", (
            f"integer target with {n_unique} distinct values, read as class labels "
            "(pass --type regression if it is a count or a score)"
        )
    return "regression", f"numeric target with {n_unique} distinct values"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fold_indices(y: pd.Series, task_type: str, folds: int, test_size: float, seed: int):
    """Yield ``(train_idx, test_idx)`` positional index arrays, one pair per fold."""
    classification = task_type != "regression"
    if folds == 1:
        idx = np.arange(len(y))
        train_idx, test_idx = train_test_split(
            idx, test_size=test_size, random_state=seed, shuffle=True,
            stratify=y.to_numpy() if classification else None,
        )
        yield np.sort(train_idx), np.sort(test_idx)
        return
    splitter = (StratifiedKFold if classification else KFold)(n_splits=folds, shuffle=True, random_state=seed)
    yield from splitter.split(np.zeros(len(y)), y.to_numpy() if classification else None)


def _yaml_str(value: str) -> str:
    # A JSON string literal is a valid YAML double-quoted scalar.
    return json.dumps(value, ensure_ascii=False)


def _benchmark_yaml(result: PrepareResult, source: Path, sha256: str, train: list[Path], test: list[Path]) -> str:
    lines = [
        "# CAML benchmark definition for your own data, written by `caml prepare-data`.",
        f"# Source: {source} (sha256 {sha256[:16]}...)",
        f"# {result.rows} rows, {result.feature_columns} feature columns, target {result.target!r} ({result.task_type}).",
        "# Use it with any command that takes --benchmark, e.g.:",
        f"#   caml sweep FLAML AutoGluon --benchmark {result.benchmark_file} --constraint test",
        "# To score with a different primary metric, add e.g. `metric: [balacc, auc]` under the task.",
        "---",
        "",
        f"- name: {result.name}",
        f"  description: {_yaml_str(f'Prepared from {source.name} by caml prepare-data')}",
        f"  folds: {result.folds}",
        "  dataset:",
        f"    target: {_yaml_str(result.target)}",
        f"    type: {result.task_type}",
        "    train:",
        *[f"      - {_yaml_str(str(p))}" for p in train],
        "    test:",
        *[f"      - {_yaml_str(str(p))}" for p in test],
        "",
    ]
    return "\n".join(lines)


def prepare_dataset(
    source: str | Path,
    target: str,
    out_dir: str | Path,
    *,
    name: str | None = None,
    task_type: str = "auto",
    folds: int = 5,
    test_size: float = 0.2,
    seed: int = 42,
    drop: Sequence[str] = (),
    force: bool = False,
    caml_version: str | None = None,
) -> PrepareResult:
    """Split ``source`` into fold files and write a benchmark YAML. See the module docstring."""
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise PrepareError(f"No such file: {source}")
    if task_type not in ("auto", *TASK_TYPES):
        raise PrepareError(f"--type must be auto or one of {TASK_TYPES}, not {task_type!r}.")
    if folds < 1:
        raise PrepareError("--folds must be at least 1.")
    if folds == 1 and not 0 < test_size < 1:
        raise PrepareError("--test-size must be between 0 and 1.")

    name = sanitize_name(name or source.stem)
    dataset_dir = Path(out_dir).expanduser().resolve() / name
    if dataset_dir.exists() and any(dataset_dir.iterdir()) and not force:
        raise PrepareError(f"{dataset_dir} already exists and is not empty; pass --force to overwrite it.")

    df = read_table(source)
    if df.columns.duplicated().any():
        dupes = sorted(set(df.columns[df.columns.duplicated()].astype(str)))
        raise PrepareError(f"Duplicate column names: {', '.join(dupes)}. Rename them first.")
    df.columns = [str(c) for c in df.columns]

    if target not in df.columns:
        close = difflib.get_close_matches(target, df.columns, n=3)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise PrepareError(f"Target column {target!r} not found.{hint} Columns: {', '.join(df.columns[:30])}")
    unknown_drop = [c for c in drop if c not in df.columns]
    if unknown_drop:
        raise PrepareError(f"--drop column(s) not found: {', '.join(unknown_drop)}")
    if target in drop:
        raise PrepareError("The target column can't also be dropped.")

    warnings: list[str] = []
    df = df.drop(columns=list(drop))
    missing_target = df[target].isna()
    dropped_rows = int(missing_target.sum())
    if dropped_rows:
        warnings.append(f"Dropped {dropped_rows} row(s) with a missing target value.")
        df = df.loc[~missing_target]
    df = df.reset_index(drop=True)
    if df.shape[1] < 2:
        raise PrepareError("No feature columns left besides the target.")

    y = df[target]
    if task_type == "auto":
        task_type, type_reason = infer_task_type(y)
    else:
        type_reason = "set explicitly with --type"
        if task_type == "regression" and not pd.api.types.is_numeric_dtype(y):
            raise PrepareError("--type regression needs a numeric target column.")
        n_unique = int(y.nunique())
        if task_type == "binary" and n_unique != 2:
            raise PrepareError(f"--type binary needs exactly 2 target values; found {n_unique}.")
        if task_type == "multiclass" and n_unique < 3:
            raise PrepareError(f"--type multiclass needs 3+ target values; found {n_unique} (use binary).")

    class_counts = None
    min_rows = max(2 * folds, 10)
    if len(df) < min_rows:
        raise PrepareError(f"Only {len(df)} usable rows; need at least {min_rows} for {folds} fold(s).")
    if task_type != "regression":
        counts = y.astype(str).value_counts()
        class_counts = {str(k): int(v) for k, v in counts.items()}
        needed = max(folds, 2)
        rare = counts[counts < needed]
        if len(rare):
            raise PrepareError(
                f"Class(es) {', '.join(map(str, rare.index[:10]))} have fewer than {needed} rows, so they can't "
                f"appear in every fold. Use fewer --folds, merge or drop rare classes, or use --type regression "
                "if the target is really numeric."
            )
        if counts.iloc[-1] / counts.iloc[0] < 0.05:
            warnings.append(
                f"Strong class imbalance (smallest class {counts.iloc[-1]} vs largest {counts.iloc[0]} rows). "
                "Consider adding `metric: [balacc, auc]` (binary) or `metric: [balacc, logloss]` to the YAML."
            )

    if task_type != "regression" and (
        pd.api.types.is_bool_dtype(y) or set(y.astype(str).str.lower().unique()) <= {"true", "false"}
    ):
        warnings.append(
            "True/False target labels: pandas turns them into booleans when the CSV is read back, which "
            "trips at least one framework (FEDOT, KI-05). Mapping them to words (e.g. yes/no) is safer."
        )

    for col in df.columns:
        if col == target:
            continue
        series = df[col]
        if "id" in re.split(r"[^a-z]+", col.lower()) and series.nunique() == len(series):
            warnings.append(f"Column {col!r} looks like a row identifier (unique per row). Consider --drop {col}.")

    dataset_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for old in dataset_dir.glob(f"{name}_t*_*.csv"):
            old.unlink()

    train_paths: list[Path] = []
    test_paths: list[Path] = []
    for k, (train_idx, test_idx) in enumerate(_fold_indices(y, task_type, folds, test_size, seed)):
        train_path = dataset_dir / f"{name}_train_{k}.csv"
        test_path = dataset_dir / f"{name}_test_{k}.csv"
        df.iloc[train_idx].to_csv(train_path, index=False)
        df.iloc[test_idx].to_csv(test_path, index=False)
        train_paths.append(train_path)
        test_paths.append(test_path)

    sha256 = _sha256(source)
    result = PrepareResult(
        name=name,
        task_type=task_type,
        type_reason=type_reason,
        target=target,
        folds=folds,
        rows=len(df),
        feature_columns=df.shape[1] - 1,
        benchmark_file=str(dataset_dir / f"{name}.yaml"),
        dataset_dir=str(dataset_dir),
        dropped_rows=dropped_rows,
        dropped_columns=list(drop),
        class_counts=class_counts,
        warnings=warnings,
    )
    Path(result.benchmark_file).write_text(_benchmark_yaml(result, source, sha256, train_paths, test_paths))
    provenance = {
        **asdict(result),
        "source": str(source),
        "source_sha256": sha256,
        "seed": seed,
        "test_size": test_size if folds == 1 else None,
        "split": "holdout" if folds == 1 else ("stratified k-fold" if task_type != "regression" else "k-fold"),
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "caml_version": caml_version,
    }
    (dataset_dir / "dataset.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return result
