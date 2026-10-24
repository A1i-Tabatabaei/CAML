# NaiveAutoML

| | |
|---|---|
| PyPI package | [`naiveautoml`](https://pypi.org/project/naiveautoml/) |
| GitHub | [fmohr/naiveautoml](https://github.com/fmohr/naiveautoml) |
| License | MIT |
| Current pin | `0.1.6` |
| Python range | `>=3.12,<3.13` (PyPI classifiers list only 3.12) |
| System deps | none |
| Status | **skipped** (confirmed-upstream bug, user's decision 2026-07-30) — see `STATUS.md` |

## Why it's in the roster

Small academic tool (Felix Mohr), fast/timeout-free greedy search — good
diversity pick against the larger search-based frameworks, low risk. Also
the clearest case in the whole roster for per-framework venv isolation:
it exact-pins `numpy<2`, `scikit-learn==1.5.2`, `configspace==1.2.0`,
directly conflicting with AutoGluon's numpy-2-era stack.

## Integration notes — real API drift from AMLB's reference

AMLB's `frameworks/NaiveAutoML/exec.py` (`automlbenchmark-reference/`)
passes `timeout=` and `execution_timeout=` to the `NaiveAutoML`
constructor. Neither exists in the current source (confirmed live against
`github.com/fmohr/naiveautoml`, 2026-07-30) — the real kwargs are
`timeout_overall` (total budget) and `timeout_candidate`
(per-candidate-pipeline timeout). CAML's `exec.py` uses the corrected
names, keeping AMLB's derivation logic (per-candidate timeout scaled from
the overall budget) intact.

Data flow follows CAML's array-based convention, passing label-encoded
`y_enc` (not raw `y`) for both splits and setting
`target_is_encoded=True`, matching AMLB's original choice.

## Status: skipped, confirmed-upstream bug

Install is clean — all four hard pins (`numpy<2`, `scikit-learn==1.5.2`,
`configspace==1.2.0`, `scikit-multilearn==0.2.0`, the last one not
released since December 2018) resolve without issue.

The smoke test surfaced two bugs:

1. **Fixed.** AMLB's `max_hpo_iterations=1e10` is a Python float; current
   `naiveautoml` does `range(self.task.max_hpo_iterations)` internally,
   which needs an int — `TypeError: 'float' object cannot be interpreted
   as an integer` on every job. `exec.py` now passes `10_000_000_000`.
   Independently corroborated:
   [github.com/fmohr/naiveautoml#75](https://github.com/fmohr/naiveautoml/issues/75)
   reports another user hitting this exact error running NaiveAutoML
   under AMLB with short time constraints.
2. **Not fixed — confirmed upstream.** After the float fix, every task
   in the test benchmark (kc2, iris, cholesterol) still fails with
   `KeyError: nan` inside `naiveautoml`'s own `fit()` method. Root cause,
   traced via a scoped single-task diagnostic: `naiveautoml.py`'s
   `as_result_for_best_candidate` is built from the single
   globally-highest-scoring row across the framework's entire per-phase
   evaluation history, not from a row that actually corresponds to the
   final decided combination of pipeline steps. When that row comes from
   an early, single-step evaluation phase, other steps' `_class` columns
   are NaN in it, and a later lookup
   (`get_config_space_for_selected_algorithms`) crashes trying to use NaN
   as a dict key. Reproduced consistently across independent runs on all
   three test-benchmark task types (binary classification, multiclass,
   regression). This is inside `naiveautoml`'s own package code — not
   something fixable from CAML's `exec.py` without forking or
   monkeypatching a third-party dependency.

**Resolved 2026-07-30**: the user decided to skip NaiveAutoML, the same
treatment as SapientML — not load-bearing for the project, and this
diagnosis is kept here in full in case `naiveautoml` ever ships an
upstream fix and the framework is worth revisiting. This was a call for
the user to make, not something to resolve unilaterally mid-session,
since it changes the framework's viability for this roster rather than
being a straightforward integration fix. See `STATUS.md`'s Framework
status table (row: `skipped`) and `CLAUDE.md`'s session handoff for the
full decision writeup.
