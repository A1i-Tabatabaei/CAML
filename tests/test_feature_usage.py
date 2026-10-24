"""Unit tests for CAML's feature-usage reporting
(``frameworks/shared/feature_usage.py``): which original input columns each
framework's final model used, standardized into the ``n_features_total``/
``n_features_used``/``features_used`` columns every touched ``exec.py``
splats into its ``result(...)`` call.

Verifiable locally without installing any AutoML package -- ``pandas``/
``scikit-learn`` are already orchestrator dev/runtime deps, and
``feature_usage.py`` itself imports nothing but stdlib.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.feature_selection import SelectKBest, VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from frameworks.shared.feature_usage import (  # noqa: E402
    feature_usage,
    union_of_branch_features,
    used_columns_from_pipeline,
)


# --------------------------------------------------------------------------
# feature_usage()
# --------------------------------------------------------------------------

def test_feature_usage_all_columns_when_used_columns_none():
    out = feature_usage(["a", "b", "c"])
    assert out == dict(n_features_total=3, n_features_used=3, features_used="a;b;c")


def test_feature_usage_subset_preserves_all_columns_order():
    out = feature_usage(["a", "b", "c"], used_columns=["c", "a"])
    assert out["features_used"] == "a;c"  # order follows all_columns, not used_columns
    assert out["n_features_used"] == 2


def test_feature_usage_drops_unknown_used_column_names():
    out = feature_usage(["a", "b"], used_columns=["a", "bogus"])
    assert out["n_features_used"] == 1
    assert out["features_used"] == "a"


def test_feature_usage_truncates_long_lists_but_keeps_exact_counts():
    cols = [f"c{i}" for i in range(200)]
    out = feature_usage(cols, max_names_shown=10)
    assert out["n_features_total"] == out["n_features_used"] == 200
    assert out["features_used"].endswith(";...(+190 more)")


def test_feature_usage_zero_used_columns():
    out = feature_usage(["a", "b"], used_columns=[])
    assert out == dict(n_features_total=2, n_features_used=0, features_used="")


# --------------------------------------------------------------------------
# used_columns_from_pipeline() -- real sklearn Pipeline, TPOT/GAMA shape
# --------------------------------------------------------------------------

def _fitted(steps):
    X = pd.DataFrame({"a": [1, 1, 1, 1], "b": [1, 2, 3, 4], "c": [5, 6, 7, 8]})
    y = [0, 1, 0, 1]
    pipe = Pipeline(steps)
    pipe.fit(X, y)
    return pipe, list(X.columns)


def test_used_columns_from_pipeline_first_selector_step():
    pipe, cols = _fitted([("sel", VarianceThreshold()), ("clf", DummyClassifier())])
    assert used_columns_from_pipeline(pipe, cols) == ["b", "c"]  # "a" has 0 variance


def test_used_columns_from_pipeline_no_selector_returns_none():
    pipe, cols = _fitted([("clf", DummyClassifier())])
    assert used_columns_from_pipeline(pipe, cols) is None


def test_used_columns_from_pipeline_selector_not_first_returns_none():
    pipe, cols = _fitted(
        [("scale", StandardScaler()), ("sel", VarianceThreshold()), ("clf", DummyClassifier())]
    )
    assert used_columns_from_pipeline(pipe, cols) is None  # conservative fallback


def test_used_columns_from_pipeline_handles_none_pipeline():
    assert used_columns_from_pipeline(None, ["a", "b"]) is None


# -- extended shapes confirmed on a real VPS, 2026-09-10 (GAMA's leading
# imputer; TPOT's FeatureUnion-wrapped candidate slots) -- added 2026-09-15


def test_used_columns_from_pipeline_selector_after_imputer():
    """GAMA shape: pipeline always imputes as step 0 before anything else."""
    pipe, cols = _fitted(
        [("impute", SimpleImputer()), ("sel", VarianceThreshold()), ("clf", DummyClassifier())]
    )
    assert used_columns_from_pipeline(pipe, cols) == ["b", "c"]


def test_used_columns_from_pipeline_selector_after_passthrough():
    """TPOT shape: unused optional slots are literal `"passthrough"` steps."""
    pipe, cols = _fitted(
        [("opt1", "passthrough"), ("sel", VarianceThreshold()), ("clf", DummyClassifier())]
    )
    assert used_columns_from_pipeline(pipe, cols) == ["b", "c"]


def test_used_columns_from_pipeline_selector_nested_in_feature_union():
    """TPOT shape: a real selector nested inside a FeatureUnion, with every
    other branch a no-op ("drop") -- confirmed structural limitation from
    2026-09-10, now handled."""
    pipe, cols = _fitted(
        [
            ("opt1", "passthrough"),
            ("fu", FeatureUnion([("skip", "drop"), ("sel", VarianceThreshold())])),
            ("clf", DummyClassifier()),
        ]
    )
    assert used_columns_from_pipeline(pipe, cols) == ["b", "c"]


def test_used_columns_from_pipeline_feature_union_mixed_branches_returns_none():
    """A FeatureUnion combining a selector's output with another real
    transformer's output can't be trusted -- the union mixes in columns the
    selector didn't choose, so this stays a conservative fallback."""
    pipe, cols = _fitted(
        [
            ("fu", FeatureUnion([("scale", StandardScaler()), ("sel", VarianceThreshold())])),
            ("clf", DummyClassifier()),
        ]
    )
    assert used_columns_from_pipeline(pipe, cols) is None


def test_used_columns_from_pipeline_multiple_selectors_returns_none():
    """More than one selector-capable point anywhere in the pipeline is
    ambiguous -- conservative fallback, same philosophy as the pre-existing
    single-selector-first-step rule."""
    pipe, cols = _fitted(
        [
            ("sel1", VarianceThreshold()),
            ("sel2", SelectKBest(k=1)),
            ("clf", DummyClassifier()),
        ]
    )
    assert used_columns_from_pipeline(pipe, cols) is None


# --------------------------------------------------------------------------
# union_of_branch_features() -- LightAutoML shape, fake leaf objects
# --------------------------------------------------------------------------

class _Leaf:
    def __init__(self, used_features=None):
        if used_features is not None:
            self.used_features = used_features


def test_union_of_branch_features_unions_when_all_present():
    result = union_of_branch_features([_Leaf(["a", "b"]), _Leaf(["b", "c"])])
    assert set(result) == {"a", "b", "c"}


def test_union_of_branch_features_falls_back_when_any_branch_missing():
    assert union_of_branch_features([_Leaf(["a"]), _Leaf()]) is None


def test_union_of_branch_features_empty_is_none():
    assert union_of_branch_features([]) is None


class _MethodLeaf:
    """LightAutoML shape: attr names a zero-arg method, not a plain attribute
    (confirmed live against TabularAutoML.collect_used_feats(), 2026-09-10)."""

    def __init__(self, used_features=None):
        self._used_features = used_features

    def collect_used_feats(self):
        return self._used_features


def test_union_of_branch_features_calls_callable_attr():
    result = union_of_branch_features(
        [_MethodLeaf(["a", "b"]), _MethodLeaf(["b", "c"])],
        attr="collect_used_feats",
    )
    assert set(result) == {"a", "b", "c"}


def test_union_of_branch_features_callable_attr_falls_back_when_empty():
    assert (
        union_of_branch_features(
            [_MethodLeaf(["a"]), _MethodLeaf([])], attr="collect_used_feats"
        )
        is None
    )
