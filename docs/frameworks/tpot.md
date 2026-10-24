# TPOT

| | |
|---|---|
| PyPI package | [`tpot`](https://pypi.org/project/TPOT/) |
| GitHub | [EpistasisLab/tpot](https://github.com/EpistasisLab/tpot) |
| License | LGPL-3.0 |
| Current pin | `1.1.0` |
| Python range | `>=3.10,<3.14` |
| System deps | none |
| Status | see `STATUS.md` |

## Why it's in the roster

Long-standing genetic-programming AutoML; TPOT2's graph-based rewrite was
merged into mainline `tpot` as v1.x in 2025.

## Integration notes — this one needed a real rewrite, not a port

AMLB's `frameworks/TPOT/exec.py` (`automlbenchmark-reference/`) targets
TPOT's pre-2025-rewrite API and does not run as-is against current TPOT.
Confirmed live against `github.com/EpistasisLab/tpot`'s current source,
2026-07-29:

- `config_dict=` constructor kwarg is gone, replaced by `search_space=`
  (e.g. `"linear"`, `"graph"`, `"mdr"`). `exec.py` uses
  `search_space="linear"` rather than trying to replicate AMLB's old
  sparse-data `config_dict` special-case, which has no direct new-API
  equivalent.
- Single-metric scoring is now `scorers=[<name>]` + `scorers_weights=[1]`
  (both lists — the new API supports multi-objective optimization)
  instead of a bare `scoring=<name>` string. The underlying sklearn
  scorer name strings themselves (`accuracy`, `roc_auc`, `neg_log_loss`,
  etc.) are unchanged.
- `tpot.evaluated_individuals_` (dict, trailing underscore) is now
  `tpot.evaluated_individuals` (pandas DataFrame, no trailing underscore)
  — used for `models_count`.
- `fitted_pipeline_` is unchanged.
- AMLB's `save_artifacts()` introspected `pareto_front_fitted_pipelines_`
  and `estimator._pareto_front` (both gone). The new
  `evaluated_individuals` DataFrame already carries Pareto-front
  membership as a column, so `exec.py`'s artifact dump just writes that
  DataFrame out instead of reconstructing the old hall-of-fame format —
  same debug intent (opt-in via `_save_artifacts`), simpler mechanism.

Data flow follows CAML's own array-based convention (`dataset.train.X`/`.y`,
same as FLAML/MLJAR), not AMLB's TPOT-specific `X_enc`/`y_enc`/`unsparsify`
handling — CAML's dataset accessors already normalize that.

## Gotchas

- **`tpot.predict()` does not round-trip in the original label space.**
  Unlike FLAML/MLJAR/AutoGluon's underlying libraries, `TPOTClassifier`'s
  `.predict()` returns its own internal integer-encoded classes (e.g.
  `0`/`1`), not the original labels `y_train` was fit with — while
  `.predict_proba()` and `truth` both stay in the original label space.
  Found the hard way: produced a 100%-reproducible `ResultError: y
  contains previously unseen labels` on every classification job until
  fixed. `exec.py` now maps `predictions` through `tpot.classes_` (the
  standard sklearn attribute) immediately after calling `.predict()`.
  `predict_proba` still raises (`RuntimeError`/`AttributeError`) when the
  winning pipeline doesn't support it at all — kept AMLB's try/except
  fallback and `__init__.py`'s `process_results` one-hot-encoding fallback
  for that case, unaffected by the rewrite.
- **Needed `setuptools<82` as an explicit steering constraint** (not a
  real TPOT dependency): `tpot`'s `stopit` sub-dependency does a bare
  `import pkg_resources` at import time, which fails on a `uv venv` (no
  setuptools preinstalled by default) combined with an unpinned/current
  setuptools — `pkg_resources` was fully removed from setuptools as of
  82.0.0 (2026-02-08). Same class of fix as MLJARSupervised's
  `numba>=0.60` steering pin.
- Bringing this framework up also surfaced a real, general bug in
  `src/caml/frameworks/installer.py` (not TPOT-specific, but TPOT was the
  first framework to need a non-`==` pin and hit it): package specs
  weren't shell-quoted before being joined into the `uv pip install`
  command, so `setuptools<82` got parsed by `/bin/sh` as I/O redirection.
  Fixed centrally with `shlex.quote()` — see
  `docs/operations/troubleshooting.md`.

## Last verified

**2026-07-30, real VPS (Ubuntu 24.04, 4 vCPU/7.8GB RAM/232GB disk)** —
`caml install TPOT && caml run TPOT --benchmark test --constraint test`
completed cleanly, all 6 jobs (kc2/iris/cholesterol × 2 folds) produced
real, plausible scores in line with FLAML/MLJAR/AutoGluon's earlier
numbers:

- kc2: AUC 0.864 / 0.934
- iris: acc 1.000 / 1.000
- cholesterol: RMSE 44.15 / 54.29

Also confirmed via `tests/test_e2e_framework_run.py` — passed.

## `validation` benchmark findings (2026-07-31 E2E audit)

Failed on the messy-data `validation` benchmark (see
`docs/operations/e2e-verification.md`), aborting after the 2nd task
(`dresses-sales`) with TPOT's own `Exception: No individuals could be
evaluated in the initial population`. `dresses-sales` is mostly
categorical with missing values in most columns; TPOT's genetic search
couldn't fit a single valid pipeline within the short `test`-constraint
budget on this data. Undetermined whether this is a too-tight time budget
for TPOT's search on hard data or a genuine preprocessing gap —
distinguishing them needs a longer-constraint re-run (e.g. `1h4c`). The
benchmark aborted here, so TPOT's behavior on the other 7 validation
tasks is unknown from this run (see the "job-runner abort behavior" note
in the audit report). Documented, not chased further in this pass.
