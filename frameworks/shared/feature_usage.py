"""Standardizes how every framework reports which original input-feature
columns its final model actually used, for CAML's benchmark reporting.

Runs *inside* a framework's isolated venv (same context as
``frameworks/shared/compute.py``) -- stdlib only, no numpy/pandas/sklearn
import, so it's always importable regardless of what a given framework's
venv happens to contain.

Every framework's exec.py calls ``feature_usage(all_columns, used_columns)``
and splats the result into its ``result(...)`` call, so ``results.csv``
always gets the same three columns with the same shape:

- ``n_features_total``  (int)
- ``n_features_used``   (int)
- ``features_used``     (str, ``;``-joined original column names, capped --
  see ``_MAX_NAMES_SHOWN``)

``used_columns=None`` means "no selection ability / not exercised under the
current config" -> reported as "used everything". This is a REPORTING-ONLY
feature: it never changes what a framework actually does.

``used_columns_from_pipeline()`` and ``union_of_branch_features()`` are
companion helpers for the two extraction *shapes* that repeat across the
roster (a fitted sklearn-Pipeline-like object with ``.steps``; a scattered
set of per-branch leaf objects). They take no framework-specific objects (no
tpot/gama/lightautoml import) purely so they can be unit-tested locally
without installing any AutoML package -- the framework-specific part (how to
*reach* the pipeline/branch objects for a given library) still lives in each
exec.py, per-framework, as it must.
"""

from typing import Iterable, Optional

# Caps the *names string* only -- n_features_total/n_features_used are always
# exact ints. Needed because CAML's own validation.yaml roster already
# includes very wide tasks (bioresponse ~1776 cols, internet-advertisements
# ~1558, micro-mass ~1300, census-income) where an uncapped joined name list
# would bloat every results.csv row by several KB, mostly for frameworks that
# used every column anyway (the "all columns" case is the one most likely to
# be huge and least informative to spell out in full).
_MAX_NAMES_SHOWN = 60


def feature_usage(
    all_columns: Iterable[str],
    used_columns: Optional[Iterable[str]] = None,
    *,
    max_names_shown: int = _MAX_NAMES_SHOWN,
) -> dict:
    """Build the three `others` kwargs for `result(...)`.

    :param all_columns: every original predictor column name the framework
        was given, in their original order (e.g. `list(X_train.columns)`).
    :param used_columns: the subset of `all_columns` the final model actually
        used. `None` => framework has no selection ability under the current
        config => "used everything". Any name not present in `all_columns`
        is silently dropped (defensive -- an extractor bug should never
        surface a bogus feature name rather than degrade to "all columns").
    """
    all_cols = list(all_columns)
    if used_columns is None:
        used_cols = list(all_cols)
    else:
        used_set = set(used_columns)
        used_cols = [c for c in all_cols if c in used_set]
    return dict(
        n_features_total=len(all_cols),
        n_features_used=len(used_cols),
        features_used=_format_names(used_cols, max_names_shown),
    )


def _format_names(names: list, max_names_shown: int) -> str:
    if len(names) <= max_names_shown:
        return ";".join(names)
    shown = names[:max_names_shown]
    return ";".join(shown) + f";...(+{len(names) - max_names_shown} more)"


# Step types confirmed (2026-09-10 real-VPS fits) to preserve column
# identity/count/order, so it's safe to walk past them while looking for a
# selector -- GAMA's pipeline always imputes as step 0 before anything else.
_IDENTITY_SAFE_STEP_NAMES = {"SimpleImputer"}


def _is_identity_safe_step(step) -> bool:
    """True for a pipeline step known not to add/drop/reorder columns --
    `"passthrough"` is sklearn's own identity-step sentinel (also `None` in
    older sklearn), confirmed to be how TPOT's linear template represents an
    unused optional slot (steps literally named `passthrough-1`,
    `passthrough-2` in a real fit). `SimpleImputer` fills values in place
    without touching column identity -- confirmed the specific step GAMA
    always places first.
    """
    if step is None or step == "passthrough":
        return True
    return type(step).__name__ in _IDENTITY_SAFE_STEP_NAMES


def _selector_in_step(step):
    """Return the feature-selector object represented by this single
    pipeline step, or None if this step isn't (confidently) one.

    A step is a selector if it exposes `.get_support()` directly. A step can
    also be a `FeatureUnion` -- TPOT's linear template wraps each optional
    candidate slot this way (confirmed 2026-09-10: real fits showed steps
    named `featureunion-1`, `featureunion-2`) -- trusted only when EXACTLY
    ONE of its branches is a selector and every other branch is empty
    (`"drop"`/`None`): a union of a selector's output with any OTHER real
    transformer's output would mix in columns the selector didn't choose,
    so that shape is not trusted and returns None.
    """
    if hasattr(step, "get_support"):
        return step
    transformer_list = getattr(step, "transformer_list", None)
    if transformer_list is None:
        return None
    branches = [est for _, est in transformer_list]
    selectors = [est for est in branches if hasattr(est, "get_support")]
    others = [est for est in branches if est not in selectors and est is not None and est != "drop"]
    if len(selectors) == 1 and not others:
        return selectors[0]
    return None


def used_columns_from_pipeline(pipeline, all_columns) -> Optional[list]:
    """TPOT/GAMA-shaped extraction: a fitted object exposing `.steps`
    (name, estimator) pairs, sklearn-Pipeline style -- true for both
    `tpot.fitted_pipeline_` and GAMA's `gama_automl.model`.

    Walks steps in order looking for exactly one selector-capable point (a
    step exposing `.get_support()`, or a `FeatureUnion` wrapping exactly one
    -- see `_selector_in_step()`), requiring every step BEFORE it to be
    identity-safe (see `_is_identity_safe_step()`) so its input is provably
    `all_columns`, unaltered by any upstream transformer. Steps after the
    selector are ignored (they operate on the already-reduced feature set,
    not the original columns). Any other shape -- no selector; more than one
    selector-capable point anywhere; a real (non-identity-safe) transformer
    before the selector -- returns None rather than guess, since composing
    column identity through an arbitrary transformer isn't attempted in v1.
    """
    steps = list(getattr(pipeline, "steps", None) or [])
    selector = None
    for _, step in steps:
        found = _selector_in_step(step)
        if found is not None:
            if selector is not None:
                return None  # more than one selector-capable point -- ambiguous
            selector = found
        elif selector is None and not _is_identity_safe_step(step):
            return None  # an untrackable transformer precedes any selector
    if selector is None:
        return None
    mask = selector.get_support()
    return [c for c, keep in zip(all_columns, mask) if keep]


def union_of_branch_features(nodes: Iterable[object], attr: str = "used_features") -> Optional[list]:
    """Given already-located leaf model/pipeline objects (framework-specific
    traversal happens in the caller), return the union of `getattr(node, attr)`
    across all of them -- or None if `nodes` is empty or ANY node doesn't
    expose `attr` (conservative: a branch we can't introspect might have used
    everything, so the whole result degrades to "all columns used" rather
    than silently under-reporting for a framework like LightAutoML's
    TabularUtilizedAutoML that blends multiple internal branches).

    `attr` may name a zero-arg method instead of a plain attribute (e.g.
    LightAutoML's `TabularAutoML.collect_used_feats()`) -- if `getattr`
    resolves to something callable, it's called and the return value used.
    """
    nodes = list(nodes)
    if not nodes:
        return None
    union: set = set()
    for node in nodes:
        used = getattr(node, attr, None)
        if callable(used):
            used = used()
        if not used:
            return None
        union.update(used)
    return list(union)
