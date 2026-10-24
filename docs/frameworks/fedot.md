# FEDOT

**Verified 2026-07-30** — Tier 2. See `STATUS.md` for the live per-session log.

| | |
|---|---|
| PyPI package | [`fedot`](https://pypi.org/project/fedot/) (pinned `0.7.5`) |
| GitHub | [aimclub/FEDOT](https://github.com/aimclub/FEDOT) |
| License | BSD-3-Clause |
| Python range | `>=3.11,<3.13` — capped below 3.13 because `fedot`'s own `scipy<1.13.0` pin has no cp313 wheel (see below) |
| System deps | none |

## Why it's in the roster

Evolutionary pipeline search, handles classification/regression/clustering/
time-series; very actively developed upstream.

## Known context (see `CLAUDE.md`) — **deliberate deviation from AMLB**

AMLB's `resources/frameworks.yaml` pins FEDOT to git `master`
(`version: 'master'`), not a PyPI release — maximally non-reproducible,
since upstream can change FEDOT's behavior with zero AMLB-side commit.
CAML pins FEDOT to its latest **PyPI release** instead, like every other
framework (see `architecture/version-pinning-policy.md`). `0.7.5` was
latest on PyPI as of 2026-07-30.

## Python version cap — real, not the PyPI classifiers

`fedot`'s own PyPI classifiers claim only 3.8–3.10, and `requires_python`
is a loose `>=3.8` with no upper bound — neither reflects the real
constraint. Confirmed live (2026-07-30) against `fedot==0.7.5`'s actual
`requirements.txt` and PyPI's file listings:

- `fedot` hard-pins `scipy<1.13.0`. The newest release under that ceiling,
  `scipy 1.12.0`, has wheels for cp39–cp312 only — no cp313 wheel at all —
  so resolving to Python 3.13 would force a from-source scipy build (the
  same class of problem as [LightAutoML's `statsmodels` pin](lightautoml.md),
  likely worse given scipy's Fortran/BLAS/LAPACK toolchain requirements).
- `fedot`'s own `thegolem==0.4.1` sub-dependency is pure Python
  (`py3-none-any` wheel) — not a version-wheel risk.
- `hyperopt==0.2.7` ships a universal `py2.py3-none-any` wheel — fine.
- `pyvis==0.2.1` has no wheel at all (sdist only), but it's a pure-Python
  package (a thin `vis.js` wrapper) — a source build of a pure-Python sdist
  needs no compiler, so this isn't a real risk either.
- `sktime` is conditionally pinned by FEDOT itself
  (`sktime==0.16.1; python_version < '3.10'`,
  `sktime>=0.16.1; python_version >= '3.10'`) — the unbounded floor on
  newer Python already sidesteps any old-version wheel gap.

`[python].range = ">=3.11,<3.13"` forces resolution to 3.12, which has a
real `scipy 1.12.0` wheel.

## API drift check against AMLB's reference — none found

Verified live against `github.com/aimclub/FEDOT` (tag `v0.7.5`), 2026-07-30.
Despite FEDOT being far more actively developed than TPOT or NaiveAutoML
(both of which had real breaking drift from AMLB's reference), the actual
API surface AMLB's `frameworks/FEDOT/exec.py` uses is unchanged:

- `Fedot.__init__`'s only *named* parameters are `problem`, `timeout`,
  `task_params`, `seed`, `logging_level`, `safe_mode`, `n_jobs` — `metric`,
  `max_pipeline_fit_time`, and `preset` (all three used by AMLB's
  reference) are not named params at all, they flow through
  `**composer_tuner_params` into `ApiParams`. That matters because
  `ApiParamsRepository.check_and_set_default_params()` raises a hard
  `KeyError` for any key not in its own `default_params` allowlist — this
  was a real thing to verify, not a formality, and all three are still
  present in that allowlist (`fedot/api/api_utils/api_params_repository.py`).
- `.fit(features=, target=)`, `.predict(features=)`,
  `.predict_proba(features=, probs_for_all_classes=)` signatures are all
  unchanged.
- `.current_pipeline.length` is inherited from
  `golem.core.dag.graph_delegate.GraphDelegate.length` (confirmed present
  in `thegolem==0.4.1`, FEDOT's own pinned version of its GOLEM dependency).
- `.history.save()` / `.history.get_leaderboard()` (used by the
  artifact-saving path, gated behind `_save_artifacts`) also confirmed
  present on `golem`'s `OptHistory` class.

`exec.py` is therefore a near-verbatim port of AMLB's own
`frameworks/FEDOT/exec.py` (the tabular path — `run_fedot_tabular` in
AMLB's `__init__.py` — only; AMLB's separate time-series `exec_ts.py` path
is out of scope, CAML's v1 roster is tabular classification/regression
only). The one real addition beyond AMLB's reference is CAML's
`measure_inference_time` wiring (same pattern as TPOT/LightAutoML), which
predates that harness feature upstream.

`dataset.train.y` is passed un-squeezed (CAML's default 2D column-vector
shape) — matching AMLB's reference exactly. Unlike FLAML/MLJAR/TPOT,
neither AMLB's FEDOT integration nor NaiveAutoML's (the other array-based
framework in this roster) squeeze it, so this was trusted rather than
speculatively changed.

## Verification status

Verified on the real VPS, 2026-07-30. One real install bug found and
fixed; zero `exec.py` bugs — the live API-drift check above paid off, the
port worked first try once the environment-level install issue (below)
was cleared.

### Install bug — `setuptools<82` steering pin (second framework needing it)

`import fedot` itself raised `ModuleNotFoundError: No module named
'pkg_resources'`, via `fedot → golem.core.tuning.simultaneous → hyperopt`
(`hyperopt/atpe.py` does a bare `import pkg_resources`). Same root cause
and same fix as [TPOT's identical bug](tpot.md): a bare `uv venv` doesn't
bundle `setuptools` at all, and `setuptools>=82.0.0` dropped
`pkg_resources` entirely even when setuptools *is* present. Added
`setuptools<82` to `[install].packages` — resolved to `setuptools==81.0.0`,
which still bundles `pkg_resources`. FEDOT is the **second** framework in
the roster to need this exact pin; worth checking for first if a future
framework's install fails the same way.

### Smoke-test scores (6/6 jobs, kc2/iris/cholesterol × 2 folds)

| Task | Fold | Metric | Score |
|---|---|---|---|
| kc2 | 0 | AUC / acc / balacc / logloss | 0.846 / 0.811 / 0.613 / 0.431 |
| kc2 | 1 | AUC / acc / balacc / logloss | 0.873 / 0.868 / 0.749 / 0.304 |
| iris | 0 | acc / logloss | 0.933 / 0.310 |
| iris | 1 | acc / logloss | 1.000 / 0.028 |
| cholesterol | 0 | RMSE / MAE / R² | 42.57 / 33.50 / 0.064 |
| cholesterol | 1 | RMSE / MAE / R² | 53.67 / 43.08 / 0.001 |

All in line with every other verified framework in the roster. `caml
doctor` clean afterward; `tests/test_e2e_framework_run.py` passing
alongside the rest of the installed roster (see `STATUS.md`).

### Non-blocking observations (not bugs)

- Every job logs `Topological features operation requires extra
  dependencies for time series forecasting, which are not installed.` —
  a FEDOT-internal notice about its own `fedot[extra]` ts-forecasting
  extras, irrelevant to CAML's tabular-only usage (see the "out of scope"
  note above). Harmless.
- The `measure_inference_time` wiring (CAML's own addition beyond AMLB's
  reference, same pattern as TPOT/LightAutoML) was **not** exercised by
  this smoke test (`measure_inference_time` defaults off in the test
  benchmark) — ported on faith from the TPOT precedent, not empirically
  verified end-to-end. Revisit if Phase 6 turns that flag on and something
  looks off.

## `validation` benchmark findings (2026-07-31 E2E audit)

Passed 7 of 9 tasks in the messy-data `validation` benchmark (see
`docs/operations/e2e-verification.md`). Two failures, both genuine:

- **`kc1` — `ResultError: y contains previously unseen labels:
  np.str_('0.0')`.** `kc1`'s target is boolean `(true, false)`; the
  prediction/truth columns get pandas-coerced through `True/False` and
  don't round-trip back to the original label space. **Same class of bug
  as TPOT's `classes_` mapping and SapientML's `predict_option` label
  handling** — plausibly fixable in `exec.py` with explicit string-dtype
  enforcement on the predicted labels. **Not fixed in the audit pass**
  (the mandate was to run the documented process and record, not to make
  new code changes mid-run); flagged here for a future FEDOT-specific fix.
- **`census-income` — OOM-killed** (7.4GB RSS on the 7.8GB box, confirmed
  via `dmesg`). A resource-limit finding, not a code bug — would likely
  pass on a bigger instance (relevant to the Phase 8 backlog). Not
  fixable at the CAML layer on this box.
