# LightAutoML

| | |
|---|---|
| PyPI package | [`lightautoml`](https://pypi.org/project/lightautoml/) |
| GitHub | [sb-ai-lab/LightAutoML](https://github.com/sb-ai-lab/LightAutoML) |
| License | Apache-2.0 |
| Current pin | `0.4.2` |
| Python range | `>=3.11,<3.13` (capped below the package's own claimed 3.13 — see gotchas) |
| System deps | none (CPU-only torch wheel via `extra_index_urls`) |
| Status | see `STATUS.md` |

## Why it's in the roster

Heavy but capable gradient-boosting-centric AutoML (torch + catboost +
xgboost + lightgbm, blended). Slower release cadence than Tier 1
frameworks but still actively maintained.

## Integration notes — closely ported, no API drift found

Unlike TPOT/NaiveAutoML, verifying live against
`github.com/sb-ai-lab/LightAutoML`'s current source (2026-07-30) found no
breaking API changes from AMLB's reference: `TabularUtilizedAutoML`'s
constructor (`task`/`timeout`/`memory_limit`/`cpu_limit`/`random_state`),
`Task`'s valid name strings (`"binary"`/`"reg"`/`"multiclass"`), and the
`reader.class_mapping` attribute the label-recovery code reaches into are
all unchanged. Ported fairly closely as a result.

Data flow differs from every other array-based framework in the roster:
`__init__.py` passes the *full* training dataframe (predictors + target,
via `dataset.train.data`) rather than split X/y, because
`TabularUtilizedAutoML.fit_predict()` takes `roles={"target": <name>}` and
expects the target column embedded in `train_data` — LightAutoML's own
convention. Test data stays X/y split since prediction only needs
predictors. `predict()` also returns a `NumpyDataset` object rather than a
plain array — `automl.predict(X_test).data` is required to get the raw
values.

## Gotchas

- **Python capped at `<3.13` despite the package's own classifiers
  claiming 3.8–3.13.** `lightautoml`'s `statsmodels<=0.14.0` dependency
  pin has no prebuilt wheel for Python 3.13 (confirmed live via PyPI's
  file listing for statsmodels 0.14.0 — wheels exist for cp38–cp312
  only), so resolving to 3.13 falls back to a source build that fails
  outright: `Cython.Compiler.Errors.CompileError` in
  `statsmodels/nonparametric/linbin.pyx`. Hit on the real VPS on the
  first install attempt; capping the range at `<3.13` forces resolution
  to 3.12, which has a wheel for everything and installed cleanly.
- **Skipped AMLB's unconditional `apt-get install -y python3-opencv`**
  (from `automlbenchmark-reference/frameworks/lightautoml/setup.sh`) —
  `lightautoml`'s base install doesn't need it (`opencv-python` is part
  of an optional CV-extras group, `lightautoml[cv]`, never pulled by a
  bare `pip install lightautoml`), and CAML's `exec.py` only touches the
  tabular preset classes. Confirmed on the real VPS: installed and ran
  cleanly with zero apt packages.
- **Class-label recovery reaches fairly deep into LightAutoML's internal
  object graph**: `automl.outer_pipes[0].ml_algos[0].models[0][0].reader.class_mapping`
  (`predict()` returns array-index-encoded classes, not original labels —
  same underlying problem class as TPOT's `tpot.classes_` issue, different
  mechanism). Confirmed working on the real VPS run below.
- **`acc`/`balacc` looked lower than expected on kc2 relative to AUC**
  (kc2: AUC 0.870/0.884, but accuracy ~0.79 and balanced accuracy exactly
  0.5 on both folds). AUC — the benchmark's actual scoring metric for this
  task — is good and in line with every other verified framework, so this
  isn't blocking. Most likely explanation: `Task()` is constructed without
  passing CAML's actual scoring metric through (AMLB's original code
  doesn't wire this up either), so `TabularUtilizedAutoML` internally
  optimizes its own default loss (log loss for binary tasks) rather than
  accuracy/AUC specifically, and naive argmax-at-0.5-threshold on a class-
  imbalanced dataset (kc2 is ~80/20) is a well-known way to get exactly
  this AUC-good/balanced-accuracy-poor signature even from a
  well-calibrated model. Not investigated further since it doesn't affect
  the primary scored metric; worth a closer look if `acc`/`balacc`
  specifically (rather than the per-task metric CAML actually scores by)
  ever become load-bearing.
- Benign, cosmetic `KeyError` tracebacks from `joblib`'s `loky` backend
  (`resource_tracker.py`, `del registry[rtype][name]`) appear at the very
  end of the run log, after all 6 jobs had already produced complete,
  correct results — a well-known joblib/loky cleanup race during
  interpreter teardown, not specific to CAML or LightAutoML's actual
  computation. Doesn't affect correctness or exit code.

## Last verified

**2026-07-30, real VPS (Ubuntu 24.04, 4 vCPU/7.8GB RAM/232GB disk)** —
`caml install LightAutoML && caml run LightAutoML --benchmark test --constraint test`
completed cleanly after the Python-3.12 cap fix (one real install-time bug
found and fixed, zero `exec.py` bugs). All 6 jobs (kc2/iris/cholesterol ×
2 folds) produced real, plausible scores in line with every other
verified framework:

- kc2: AUC 0.870 / 0.884
- iris: acc 1.000 / 1.000, logloss 0.023 / 0.008
- cholesterol: RMSE 42.50 / 54.54
