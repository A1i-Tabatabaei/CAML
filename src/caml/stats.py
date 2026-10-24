"""Statistical significance testing for comparing AutoML frameworks'
benchmark results (paired PER TASK, never per fold -- folds are repeated
measurements of the same task, not independent samples of "how good is
this framework in general"; pooling them directly would pseudoreplicate
and inflate significance. See Demšar, "Statistical Comparisons of
Classifiers over Multiple Data Sets" (JMLR 2006) for the standard
methodology this follows: Wilcoxon signed-rank for two-way comparisons,
Friedman + a corrected pairwise post-hoc for three-or-more-way ones.

Pure pandas/numpy/scipy -- no ``caml.*`` imports, no ``Scoreboard``/
framework objects -- so it's directly unit-testable with constructed
DataFrames, same philosophy as ``frameworks/shared/feature_usage.py``.
The CLI (``caml compare``, ``src/caml/cli.py``) is the only caller that
touches ``Scoreboard``/``output/results.csv``; everything here takes/
returns plain pandas/dict structures.

Every function here reads ``result`` (not any per-metric column like
``auc``/``rmse``) -- ``TaskResult.compute_score()`` already
direction-normalizes it to "higher is better" for every metric (negating
+ ``neg_``-prefixing metrics where lower is better), so it's safe to
compare directly across frameworks without re-deriving metric direction.
It is NOT scale-normalized across metric families, though -- a
``neg_rmse`` difference of 5 and an ``auc`` difference of 0.02 are not on
a comparable scale. Wilcoxon/Friedman only use the *rank* of paired
differences, which tolerates this; the paired t-test uses raw magnitude
and is therefore less trustworthy whenever a compared task set mixes
classification and regression tasks -- callers should surface that
caveat rather than presenting both p-values with equal authority.
"""

from __future__ import annotations

import itertools
import math
import warnings
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

MIN_PAIRED_TASKS = 2
MIN_FRAMEWORKS_FOR_OMNIBUS = 3


def per_task_scores(
    df: pd.DataFrame, frameworks: Sequence[str]
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Reduce raw per-fold rows (columns: ``task``/``framework``/``result``)
    to one paired sample per task: the mean ``result`` across that task's
    folds, for each of `frameworks`.

    Averages ALL matching rows currently in `df`, including any repeated
    historical ``caml run`` invocations of the same task/fold --
    ``results.csv`` is append-only and not deduplicated across sessions.
    This is a deliberate scope decision (documented in
    ``docs/reference/cli.md``), not an oversight: scoping to one specific
    run is a filtering job for the caller (e.g. via ``--constraint``, or
    pre-filtering `df` by ``utc``), not this function's.

    :return: ``(scores, excluded)``.
      ``scores`` is a DataFrame indexed by task name, one column per
      framework (in `frameworks` order), restricted to tasks with a
      non-NaN mean result for EVERY requested framework (inner join
      across frameworks).
      ``excluded`` maps ``{task_name: [frameworks missing for that
      task]}`` for every task with data for at least one but not all
      requested frameworks.
    """
    frameworks = list(frameworks)
    subset = df[df["framework"].isin(frameworks)]
    pivoted = (
        subset.groupby(["task", "framework"])["result"]
        .mean()
        .unstack("framework")
        .reindex(columns=frameworks)
    )
    if pivoted.empty:
        return pivoted, {}

    complete = pivoted.notna().all(axis=1)
    scores = pivoted[complete]
    excluded = {
        task: [fw for fw in frameworks if pd.isna(row[fw])]
        for task, row in pivoted[~complete].iterrows()
    }
    return scores, excluded


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Holm step-down family-wise-error-rate correction. Returns adjusted
    p-values in the SAME ORDER as `p_values` -- compare each directly
    against alpha to decide rejection. Hand-rolled (no `scikit-posthocs`/
    `statsmodels` dependency) -- equivalent to R's
    ``p.adjust(method="holm")`` / statsmodels'
    ``multipletests(method="holm")``.
    """
    p_values = list(p_values)
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted: list[float] = [0.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        running_max = max(running_max, (m - rank) * p_values[idx])
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def _win_tie_stats(a: np.ndarray, b: np.ndarray) -> dict:
    diffs = a - b
    return dict(
        wins_a=int((diffs > 0).sum()),
        wins_b=int((diffs < 0).sum()),
        ties=int((diffs == 0).sum()),
        mean_diff=float(diffs.mean()),
    )


def compare_pairwise(
    scores: pd.DataFrame, framework_a: str, framework_b: str, alpha: float = 0.05
) -> dict:
    """Compare two frameworks over the paired per-task scores in `scores`
    (as returned by `per_task_scores`, already complete for this pair --
    every row has both columns present).

    Descriptive fields (wins/ties/mean_diff) are always populated once
    ``n_tasks >= 1``; the p-value fields are gated behind
    ``n_tasks >= MIN_PAIRED_TASKS`` and a zero-variance pre-check
    (``np.allclose``, not a bare try/except -- the resolved scipy version
    does not raise on an all-identical paired sample, it emits a
    `RuntimeWarning` and returns ``(0.0, 1.0)``/``(nan, nan)``, confirmed
    empirically against scipy 1.18.0). ``status`` is one of ``"ok"``,
    ``"insufficient_data"``, ``"no_variance"``, ``"no_data"``.
    """
    tasks = list(scores.index)
    n_tasks = len(tasks)
    result = dict(
        mode="pairwise",
        framework_a=framework_a,
        framework_b=framework_b,
        tasks=tasks,
        n_tasks=n_tasks,
        wins_a=0,
        wins_b=0,
        ties=0,
        mean_diff=None,
        wilcoxon=None,
        ttest_rel=None,
        status="no_data",
        reason="No shared tasks with results for both frameworks.",
    )
    if n_tasks == 0:
        return result

    a = scores[framework_a].to_numpy(dtype=float)
    b = scores[framework_b].to_numpy(dtype=float)
    result.update(_win_tie_stats(a, b))
    result["reason"] = None

    if n_tasks < MIN_PAIRED_TASKS:
        result["status"] = "insufficient_data"
        result["reason"] = (
            f"Only {n_tasks} shared task(s); need at least "
            f"{MIN_PAIRED_TASKS} for a significance test."
        )
        return result

    if np.allclose(a, b):
        result["status"] = "no_variance"
        result["reason"] = "All paired scores are identical -- no measurable difference to test."
        return result

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            w_stat, w_p = scipy_stats.wilcoxon(a, b)
            if not math.isnan(w_p):
                result["wilcoxon"] = dict(
                    statistic=float(w_stat), p_value=float(w_p), significant=bool(w_p < alpha)
                )
        except ValueError:
            pass
        try:
            t_stat, t_p = scipy_stats.ttest_rel(a, b)
            if not math.isnan(t_p):
                result["ttest_rel"] = dict(
                    statistic=float(t_stat), p_value=float(t_p), significant=bool(t_p < alpha)
                )
        except ValueError:
            pass

    result["status"] = "ok"
    return result


def compare_omnibus(scores: pd.DataFrame, frameworks: Sequence[str], alpha: float = 0.05) -> dict:
    """Compare 3+ frameworks over the paired per-task scores in `scores`
    (as returned by `per_task_scores`). Raises `ValueError` for fewer than
    `MIN_FRAMEWORKS_FOR_OMNIBUS` frameworks -- routing pairwise-vs-omnibus
    is `compare()`'s job; this is a contract check, not user-input
    validation.

    Mean rank (1 = best) is always computed once ``n_tasks >= 1``,
    independent of whether the Friedman test itself can run. Post-hoc
    pairwise Wilcoxon (via `compare_pairwise`) reuses this SAME per-task
    score matrix -- the textbook-correct choice for a Friedman+post-hoc
    family, not a shortcut. Only pairs whose Wilcoxon p-value actually
    computed enter the Holm-Bonferroni correction's family size -- a pair
    excluded for insufficient/zero-variance data is reported with
    ``adjusted_p=None``, never silently treated as p=1 or dropped (which
    would understate the correction for the pairs that DID compute).
    """
    frameworks = list(frameworks)
    if len(frameworks) < MIN_FRAMEWORKS_FOR_OMNIBUS:
        raise ValueError(
            f"compare_omnibus() requires at least {MIN_FRAMEWORKS_FOR_OMNIBUS} "
            f"frameworks, got {len(frameworks)}."
        )

    tasks = list(scores.index)
    n_tasks = len(tasks)
    result = dict(
        mode="omnibus",
        frameworks=frameworks,
        tasks=tasks,
        n_tasks=n_tasks,
        mean_rank=None,
        friedman=None,
        status="no_data",
        reason="No shared tasks with results for every framework.",
        posthoc=None,
    )
    if n_tasks == 0:
        return result

    ranks = scores[frameworks].rank(axis=1, ascending=False)
    result["mean_rank"] = {fw: float(ranks[fw].mean()) for fw in frameworks}
    result["reason"] = None

    if n_tasks < MIN_PAIRED_TASKS:
        result["status"] = "insufficient_data"
        result["reason"] = (
            f"Only {n_tasks} shared task(s); need at least {MIN_PAIRED_TASKS}."
        )
    else:
        columns = [scores[fw].to_numpy(dtype=float) for fw in frameworks]
        if all(np.allclose(col, columns[0]) for col in columns):
            result["status"] = "no_variance"
            result["reason"] = "All frameworks have identical scores on every shared task."
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    f_stat, f_p = scipy_stats.friedmanchisquare(*columns)
                    if not math.isnan(f_p):
                        result["friedman"] = dict(
                            statistic=float(f_stat), p_value=float(f_p), significant=bool(f_p < alpha)
                        )
                except ValueError:
                    pass
            result["status"] = "ok"

    posthoc = []
    for fa, fb in itertools.combinations(frameworks, 2):
        pair = compare_pairwise(scores[[fa, fb]], fa, fb, alpha=alpha)
        posthoc.append(
            dict(
                framework_a=fa,
                framework_b=fb,
                wilcoxon_p=pair["wilcoxon"]["p_value"] if pair["wilcoxon"] else None,
                adjusted_p=None,
                significant=None,
                status=pair["status"],
            )
        )
    computable = [e for e in posthoc if e["wilcoxon_p"] is not None]
    if computable:
        adjusted = holm_bonferroni([e["wilcoxon_p"] for e in computable])
        for entry, adj_p in zip(computable, adjusted):
            entry["adjusted_p"] = adj_p
            entry["significant"] = bool(adj_p < alpha)
    result["posthoc"] = posthoc

    return result


def compare(df: pd.DataFrame, frameworks: Iterable[str], alpha: float = 0.05) -> dict:
    """Top-level entry point: compare 2+ frameworks' results in `df`
    (a DataFrame shaped like ``Scoreboard.as_data_frame()``'s output, at
    minimum columns ``task``/``framework``/``result``). De-duplicates
    `frameworks` (order preserved), routes to `compare_pairwise` for
    exactly 2 or `compare_omnibus` for 3+, and raises `ValueError` for
    fewer than 2 distinct frameworks.
    """
    seen: list[str] = []
    for fw in frameworks:
        if fw not in seen:
            seen.append(fw)
    if len(seen) < 2:
        raise ValueError(f"compare() requires at least 2 distinct frameworks, got {len(seen)}.")

    scores, excluded = per_task_scores(df, seen)
    if len(seen) == 2:
        result = compare_pairwise(scores, seen[0], seen[1], alpha=alpha)
    else:
        result = compare_omnibus(scores, seen, alpha=alpha)
    result["excluded_tasks"] = excluded
    return result
