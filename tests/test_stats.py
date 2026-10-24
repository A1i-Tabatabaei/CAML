"""Unit tests for CAML's significance-testing module (``src/caml/stats.py``):
comparing 2+ frameworks' benchmark results, paired per task. Constructed
fixtures with hand-verified expected values (exact Wilcoxon/Friedman
p-values, hand-computed Holm-Bonferroni corrections) rather than mocks --
same "real objects, known answers" philosophy as
``tests/test_feature_usage.py``.
"""

import numpy as np
import pandas as pd
import pytest

from caml.stats import (
    compare,
    compare_omnibus,
    compare_pairwise,
    holm_bonferroni,
    per_task_scores,
)


def _rows(*records):
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------
# per_task_scores()
# --------------------------------------------------------------------------

def test_per_task_scores_averages_folds():
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=0.8),
        dict(task="t1", framework="A", fold=1, result=0.6),
        dict(task="t1", framework="B", fold=0, result=0.5),
        dict(task="t1", framework="B", fold=1, result=0.5),
    )
    scores, excluded = per_task_scores(df, ["A", "B"])
    assert scores.loc["t1", "A"] == pytest.approx(0.7)
    assert scores.loc["t1", "B"] == pytest.approx(0.5)
    assert excluded == {}


def test_per_task_scores_excludes_task_missing_for_one_framework():
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=0.8),
        dict(task="t1", framework="B", fold=0, result=0.5),
        dict(task="t2", framework="A", fold=0, result=0.9),
        # no B row for t2
    )
    scores, excluded = per_task_scores(df, ["A", "B"])
    assert list(scores.index) == ["t1"]
    assert excluded == {"t2": ["B"]}


def test_per_task_scores_skips_nan_folds():
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=0.8),
        dict(task="t1", framework="A", fold=1, result=np.nan),
        dict(task="t1", framework="B", fold=0, result=0.5),
    )
    scores, excluded = per_task_scores(df, ["A", "B"])
    assert scores.loc["t1", "A"] == pytest.approx(0.8)


def test_per_task_scores_averages_across_repeated_historical_rows():
    """results.csv is append-only and not deduplicated across sessions --
    two rows for the identical (task, framework, fold) from two different
    `caml run` invocations must both be blended into the mean (documented
    v1 design decision, not a bug)."""
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=1.0, utc="2026-07-01"),
        dict(task="t1", framework="A", fold=0, result=0.0, utc="2026-09-01"),
        dict(task="t1", framework="B", fold=0, result=0.5, utc="2026-07-01"),
    )
    scores, _ = per_task_scores(df, ["A", "B"])
    assert scores.loc["t1", "A"] == pytest.approx(0.5)


def test_per_task_scores_empty_when_no_matching_rows():
    df = _rows(dict(task="t1", framework="C", fold=0, result=0.8))
    scores, excluded = per_task_scores(df, ["A", "B"])
    assert scores.empty
    assert excluded == {}


# --------------------------------------------------------------------------
# holm_bonferroni()
# --------------------------------------------------------------------------

def test_holm_bonferroni_hand_computed_example():
    adjusted = holm_bonferroni([0.01, 0.04, 0.03, 0.005])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_bonferroni_single_value_unchanged():
    assert holm_bonferroni([0.02]) == pytest.approx([0.02])


def test_holm_bonferroni_caps_at_one():
    # (2-0)*0.6=1.2 -> capped to 1.0; the running-max step then floors the
    # second (larger) p-value's adjustment at that same 1.0 too, per Holm's
    # monotonicity requirement (matches R's p.adjust(method="holm")).
    adjusted = holm_bonferroni([0.6, 0.7])
    assert all(p <= 1.0 for p in adjusted)
    assert adjusted == pytest.approx([1.0, 1.0])


# --------------------------------------------------------------------------
# compare_pairwise()
# --------------------------------------------------------------------------

def _scores(**framework_to_values):
    n = len(next(iter(framework_to_values.values())))
    index = [f"t{i}" for i in range(1, n + 1)]
    return pd.DataFrame(framework_to_values, index=index)


def test_compare_pairwise_known_significant_case():
    # a always beats b, 8 distinct-magnitude diffs, no ties -> exact
    # two-sided Wilcoxon p = 2 * (1/2)**8 (verified directly against scipy).
    scores = _scores(A=[1, 2, 3, 4, 5, 6, 7, 8], B=[0, 0, 0, 0, 0, 0, 0, 0])
    result = compare_pairwise(scores, "A", "B")
    assert result["status"] == "ok"
    assert result["wilcoxon"]["p_value"] == pytest.approx(0.0078125)
    assert result["wilcoxon"]["significant"] is True
    assert result["wins_a"] == 8 and result["wins_b"] == 0 and result["ties"] == 0


def test_compare_pairwise_known_nonsignificant_case():
    scores = _scores(A=[5, 3, 6, 2, 7, 1], B=[3, 5, 2, 6, 1, 7])
    result = compare_pairwise(scores, "A", "B")
    assert result["status"] == "ok"
    assert result["wilcoxon"]["p_value"] > 0.05
    assert result["wilcoxon"]["significant"] is False


def test_compare_pairwise_no_data():
    scores = pd.DataFrame(columns=["A", "B"])
    result = compare_pairwise(scores, "A", "B")
    assert result["status"] == "no_data"
    assert result["n_tasks"] == 0
    assert result["wilcoxon"] is None
    assert result["mean_diff"] is None


def test_compare_pairwise_insufficient_data_still_reports_descriptives():
    scores = _scores(A=[0.9], B=[0.7])
    result = compare_pairwise(scores, "A", "B")
    assert result["status"] == "insufficient_data"
    assert result["n_tasks"] == 1
    assert result["wilcoxon"] is None
    assert result["wins_a"] == 1
    assert result["mean_diff"] == pytest.approx(0.2)


def test_compare_pairwise_no_variance_leaks_no_warning(recwarn):
    scores = _scores(A=[0.5, 0.5, 0.5], B=[0.5, 0.5, 0.5])
    result = compare_pairwise(scores, "A", "B")
    assert result["status"] == "no_variance"
    assert result["wilcoxon"] is None
    assert result["ttest_rel"] is None
    assert len(recwarn) == 0


def test_compare_pairwise_win_tie_counts():
    scores = _scores(A=[5, 5, 3], B=[3, 7, 3])
    result = compare_pairwise(scores, "A", "B")
    assert result["wins_a"] == 1
    assert result["wins_b"] == 1
    assert result["ties"] == 1
    assert result["mean_diff"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# compare_omnibus()
# --------------------------------------------------------------------------

def test_compare_omnibus_requires_at_least_three():
    scores = _scores(A=[1, 2], B=[2, 1])
    with pytest.raises(ValueError):
        compare_omnibus(scores, ["A", "B"])


def test_compare_omnibus_mean_rank_known_fixture():
    # A always best, C always middle, B always worst.
    scores = _scores(A=[9, 8, 7], B=[5, 4, 3], C=[7, 6, 5])
    result = compare_omnibus(scores, ["A", "B", "C"])
    assert result["mean_rank"] == pytest.approx({"A": 1.0, "B": 3.0, "C": 2.0})


def test_compare_omnibus_known_significant_case():
    scores = _scores(A=[9, 8, 9, 8, 9, 8], B=[5, 4, 5, 4, 5, 4], C=[7, 6, 7, 6, 7, 6])
    result = compare_omnibus(scores, ["A", "B", "C"])
    assert result["status"] == "ok"
    assert result["friedman"]["statistic"] == pytest.approx(12.0)
    assert result["friedman"]["p_value"] == pytest.approx(0.002478752176666357)
    assert result["friedman"]["significant"] is True


def test_compare_omnibus_known_nonsignificant_case():
    # Perfectly balanced rotation: each framework is best on exactly one
    # task, mean ranks tie -> Friedman statistic is exactly 0.
    scores = _scores(A=[3, 1, 2], B=[2, 3, 1], C=[1, 2, 3])
    result = compare_omnibus(scores, ["A", "B", "C"])
    assert result["friedman"]["statistic"] == pytest.approx(0.0)
    assert result["friedman"]["p_value"] == pytest.approx(1.0)
    assert result["friedman"]["significant"] is False


def test_compare_omnibus_insufficient_data():
    scores = _scores(A=[1], B=[2], C=[3])
    result = compare_omnibus(scores, ["A", "B", "C"])
    assert result["status"] == "insufficient_data"
    assert result["mean_rank"] is not None  # descriptive field still populated


def test_compare_omnibus_no_variance_leaks_no_warning(recwarn):
    scores = _scores(A=[5, 5, 5], B=[5, 5, 5], C=[5, 5, 5])
    result = compare_omnibus(scores, ["A", "B", "C"])
    assert result["status"] == "no_variance"
    assert result["friedman"] is None
    assert len(recwarn) == 0


def test_compare_omnibus_posthoc_adjusted_p_never_below_raw_p():
    scores = _scores(A=[9, 8, 9, 8, 9, 8], B=[5, 4, 5, 4, 5, 4], C=[7, 6, 7, 6, 7, 6])
    result = compare_omnibus(scores, ["A", "B", "C"])
    for entry in result["posthoc"]:
        if entry["wilcoxon_p"] is not None:
            assert entry["adjusted_p"] >= entry["wilcoxon_p"] - 1e-12


def test_compare_omnibus_degenerate_pair_excluded_from_holm_family():
    """A and C are identical on every task (zero variance -> untestable);
    A-B and B-C are both real, equal-magnitude comparisons. The Holm
    correction family must be sized 2 (A-B, B-C), NOT 3 -- including the
    untestable A-C pair (e.g. as a phantom p=1) would wrongly inflate the
    correction applied to the two pairs that DID compute (0.375 instead of
    the correct 0.25 -- verified by hand against holm_bonferroni([0.125, 0.125])).
    """
    scores = _scores(A=[9, 8, 7, 10], B=[5, 4, 3, 6], C=[9, 8, 7, 10])
    result = compare_omnibus(scores, ["A", "B", "C"])

    by_pair = {(e["framework_a"], e["framework_b"]): e for e in result["posthoc"]}
    ac = by_pair[("A", "C")]
    assert ac["wilcoxon_p"] is None
    assert ac["adjusted_p"] is None
    assert ac["status"] == "no_variance"

    ab = by_pair[("A", "B")]
    bc = by_pair[("B", "C")]
    assert ab["wilcoxon_p"] == pytest.approx(0.125)
    assert bc["wilcoxon_p"] == pytest.approx(0.125)
    assert ab["adjusted_p"] == pytest.approx(0.25)
    assert bc["adjusted_p"] == pytest.approx(0.25)


# --------------------------------------------------------------------------
# compare() dispatcher
# --------------------------------------------------------------------------

def test_compare_two_frameworks_routes_pairwise():
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=0.9),
        dict(task="t1", framework="B", fold=0, result=0.5),
        dict(task="t2", framework="A", fold=0, result=0.8),
        dict(task="t2", framework="B", fold=0, result=0.4),
    )
    result = compare(df, ["A", "B"])
    assert result["mode"] == "pairwise"
    assert result["excluded_tasks"] == {}


def test_compare_three_frameworks_routes_omnibus():
    df = _rows(
        *[dict(task=f"t{i}", framework=fw, fold=0, result=v)
          for i, (a, b, c) in enumerate([(9, 5, 7), (8, 4, 6), (9, 5, 7)], start=1)
          for fw, v in [("A", a), ("B", b), ("C", c)]]
    )
    result = compare(df, ["A", "B", "C"])
    assert result["mode"] == "omnibus"


def test_compare_dedups_preserving_order():
    df = _rows(
        dict(task="t1", framework="A", fold=0, result=0.9),
        dict(task="t1", framework="B", fold=0, result=0.5),
    )
    result = compare(df, ["A", "B", "A"])
    assert result["mode"] == "pairwise"
    assert result["framework_a"] == "A"
    assert result["framework_b"] == "B"


def test_compare_raises_for_fewer_than_two_distinct():
    df = _rows(dict(task="t1", framework="A", fold=0, result=0.9))
    with pytest.raises(ValueError):
        compare(df, ["A", "A"])
