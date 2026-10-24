# AutoGluon

| | |
|---|---|
| PyPI package | [`autogluon.tabular`](https://pypi.org/project/autogluon.tabular/) |
| GitHub | [autogluon/autogluon](https://github.com/autogluon/autogluon) |
| License | Apache-2.0 |
| Current pin | `1.5.0` |
| Python range | `>=3.11,<3.13` |
| System deps | none |
| Status | see `STATUS.md` |

## Why it's in the roster

Flagship general-purpose tabular AutoML, largest dependency tree in the v1
set. Tabular-only bring-up (`autogluon.tabular[all]`, not the full
`autogluon` meta-package) since CAML v1 has no time-series benchmark — see
`framework.toml` for the full reasoning.

## Integration notes

`exec.py` is ported near-verbatim from AMLB's `frameworks/AutoGluon/exec.py`
(tabular path only, time-series branch dropped) — the `TabularPredictor`
fit/predict/leaderboard API is unchanged against autogluon.tabular 1.5.0.
Unlike FLAML/MLJAR, data is passed as parquet file paths + target column
metadata, not X/y arrays — matching how AutoGluon actually consumes data.

Bringing this up required a real fix in `src/caml/datasets/openml.py`
(`_oml_cached_file_base()`): openml-python >=0.15 no longer populates
`_oml_dataset.data_file`, which the original AMLB-derived dataset-splitter
logic needed to construct per-fold file paths. FLAML/MLJAR never hit this
since their array-based splitters take a different code path.

## Gotchas

- `autogluon.tabular[all]` pulls the full torch stack for its NN models.
  **Phase 6, 2026-07-30**: forced the CPU-only wheel via `extra_index_urls
  = ["https://download.pytorch.org/whl/cpu"]` (same fix as LightAutoML),
  reversing an earlier deferral. Verified on the real VPS after
  `caml uninstall AutoGluon && caml install AutoGluon`: `torch==2.9.1+cpu`,
  `torch.version.cuda is None`, zero `nvidia-*` packages pulled (`pip list
  | grep -i nvidia` empty) — venv totals 2.7GB (full tabular[all] stack:
  catboost/lightgbm/xgboost/ray/transformers, not just torch). Re-ran the
  full smoke test afterward: all 6 jobs produced scores identical to the
  pre-fix run (kc2 AUC 0.853/0.932, iris acc 0.933/1.000, cholesterol RMSE
  44.16/54.65) — the wheel swap is disk/bandwidth-only, no behavior change.
- **NeuralNetFastAI fails 100% of the time under this exact pin** —
  `fastai==2.8.7` + `fastcore==2.1.10` (both AutoGluon 1.5.0's own resolved
  transitive deps, not something CAML pins directly) have a real
  incompatibility: `AttributeError: 'list' object has no attribute
  'starmap'` inside `fastcore`'s `L.starmap`, called from fastai's
  optimizer setup during `fit_one_cycle`. **Confirmed upstream
  AutoGluon/fastai/fastcore bug, not a CAML issue** — reproduced on every
  one of 6 jobs, 2026-07-29. AutoGluon's own per-model exception handling
  catches it and excludes NeuralNetFastAI from the ensemble automatically
  ("Skipping this model"), so the benchmark still completes with real,
  correct scores from its other ~8 model types (CatBoost, LightGBM
  variants, XGBoost, NeuralNetTorch, RandomForest, ExtraTrees,
  WeightedEnsemble). Net effect: the FastAI-specific neural net variant
  never contributes to any AutoGluon result under this pin, even though
  `[all]` extras were chosen specifically to include it (see
  `framework.toml`). Not fixed here — a fix would mean deviating from
  AutoGluon's own declared dependency spec, which is a call worth the
  user's sign-off, not a unilateral one. Revisit if AutoGluon ever bumps
  its fastai/fastcore pins.
- A `sklearn` `UserWarning: The y_prob values do not sum to one` surfaces
  during metric scoring on at least one classification job. Scores still
  came back real and plausible (see below); noted but not chased further.

## Last verified

**2026-07-29, real VPS (Ubuntu 24.04, 4 vCPU/7.8GB RAM/232GB disk)** —
`caml install AutoGluon && caml run AutoGluon --benchmark test --constraint
test` completed cleanly, all 6 jobs (kc2/iris/cholesterol × 2 folds)
produced real, plausible scores in line with FLAML/MLJAR's earlier numbers:

- kc2: AUC 0.853 / 0.932
- iris: acc 0.933 / 1.000
- cholesterol: RMSE 44.16 / 54.65

Also confirmed via `tests/test_e2e_framework_run.py` (the new parametrized
pytest E2E test, not just the manual CLI invocation) — passed.

**Re-verified 2026-07-30 (Phase 6)** after the CPU-only torch wheel fix
(see Gotchas) — re-ran `caml run AutoGluon --benchmark test --constraint
test` end-to-end on the real VPS post-reinstall; all 6 jobs produced
scores identical to the original verification above, confirming the
wheel swap changed nothing behaviorally.
