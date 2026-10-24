# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Not a close port -- AMLB's own SapientML/exec.py (both the generic
# openml/automlbenchmark copy and the SapientML team's own fork) reads raw
# CSVs from disk and never wires up config.seed/config.metric/
# config.max_runtime_seconds at all. Rewritten against the current live
# SapientML/SapientMLConfig API (0.4.17/0.8.0, verified 2026-07-31) with
# those three actually wired up, and a real bug in both AMLB references
# fixed: their one-hot "probabilities" hack fits the encoder on predicted
# labels alone and assumes every class was predicted at least once, which
# isn't guaranteed on a small test fold. See docs/frameworks/sapientml.md
# Part 2 for the full reasoning behind every deviation below.

import logging
import os
import re
import tempfile as tmp

import pandas as pd
from sapientml import SapientML
from sklearn.preprocessing import OneHotEncoder

from frameworks.shared.callee import (
    call_run,
    result,
    output_subdir,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage
from frameworks.shared.utils import Timer

# Kept from the AMLB reference: sapientml-core's dependency tree
# (catboost/lightgbm/xgboost/numba all loaded into one venv) can
# oversubscribe threads against each other on a small VPS if left to their
# own defaults.
os.environ["JOBLIB_TEMP_FOLDER"] = tmp.gettempdir()
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

log = logging.getLogger(__name__)


def get_sapientml_metric(metric, task_type):
    """Map CAML/AMLB metric names to SapientML's adaptation_metric strings.

    Same defensive pattern as frameworks/AutoGluon/exec.py's
    get_autogluon_metric() -- SapientML's own Metric.get() hard-raises on
    anything unrecognized (unlike AutoGluon's more forgiving lookup), so an
    unmapped metric falls back to a sensible per-task-type default instead
    of being passed through blind. See docs/frameworks/sapientml.md Part 2
    for the full translation table and why each fallback was chosen.
    """
    metrics_mapping = dict(
        auc="auc",
        logloss="LogLoss",
        acc="accuracy",
        balacc="accuracy",  # no balanced-accuracy metric in SapientML
        rmse="RMSE",
        r2="r2",
        mae="MAE",
        mse="RMSE",  # no plain MSE in SapientML
        f1="f1",
        rmsle="RMSLE",
    )
    if metric in metrics_mapping:
        return metrics_mapping[metric]
    fallback = "accuracy" if task_type == "classification" else "r2"
    log.warning(
        f"Metric '{metric}' has no known SapientML equivalent. Falling "
        f"back to '{fallback}'. See docs/frameworks/sapientml.md Part 2 "
        f"for the full translation table."
    )
    return fallback


def sanitize(name: str) -> str:
    """Strip characters SapientML's generated pipeline code can't use as a
    column identifier. Kept from the AMLB reference for a real reason:
    SapientML emits actual Python source referencing column names -- see
    docs/frameworks/sapientml.md Part 2, Design decision #2."""
    return re.sub(r"[^A-Za-z0-9_.]+", "", name)


def run(dataset, config):
    log.info("\n**** SapientML ****\n")

    is_classification = config.type == "classification"
    task_type = "classification" if is_classification else "regression"

    training_params = {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    training_params.setdefault("seed_for_model", config.seed)
    # SapientML has no single time-budget parameter; initial_timeout is the
    # closest real knob (per-candidate-pipeline execution timeout, default
    # 600s x n_models=3 candidates). Full budget per candidate, not divided
    # -- see docs/frameworks/sapientml.md Part 2, Design decision #4.
    training_params.setdefault("initial_timeout", config.max_runtime_seconds)
    # Confirmed empirically, 2026-07-31: with predict_option left at its
    # own default (None, "comply with metric requirements"), a
    # probability-needing adaptation_metric (auc/logloss/ROC_AUC/Gini/
    # MAP_K) makes SapientML select a pipeline whose predict() output
    # shape is NOT a single target_col of hard labels -- kc2 (auc) came
    # back with raw probability floats in that column; iris (logloss)
    # came back with a DataFrame that didn't even have a target_col key
    # at all (KeyError). Forcing "default" pins the output to always be a
    # single column of hard labels regardless of adaptation_metric,
    # matching every assumption the rest of this file makes (the one-hot
    # pseudo-probability construction below needs hard labels as input).
    # See docs/frameworks/sapientml.md Part 2, Design decision #3.
    training_params.setdefault("predict_option", "default")

    train_df = dataset.train.data.copy()
    X_test = dataset.test.X.copy()
    y_test = dataset.test.y.squeeze()

    # Snapshot BEFORE the sanitize()-based rename below -- otherwise the
    # feature-usage report would leak SapientML's internal sanitized column
    # identifiers instead of the dataset's real column names.
    all_columns = list(X_test.columns)

    rename_map = {col: sanitize(col) for col in train_df.columns}
    train_df.columns = [rename_map[c] for c in train_df.columns]
    X_test.columns = [rename_map.get(c, sanitize(c)) for c in X_test.columns]
    target_col = rename_map[dataset.target.name]

    output_dir = output_subdir("sapientml_outputs", config)
    adaptation_metric = get_sapientml_metric(config.metric, task_type)

    predictor = SapientML(
        [target_col],
        task_type=task_type,
        adaptation_metric=adaptation_metric,
        **training_params,
    )

    with Timer() as training:
        predictor.fit(train_df, output_dir=output_dir)
    log.info(f"Finished fit in {training.duration}s.")

    def infer(data):
        data = pd.read_parquet(data) if isinstance(data, str) else data.copy()
        data.columns = [rename_map.get(c, sanitize(c)) for c in data.columns]
        return predictor.predict(data)[target_col]

    inference_times = {}
    if config.measure_inference_time:
        inference_times["file"] = measure_inference_times(
            infer, dataset.inference_subsample_files
        )
        inference_times["df"] = measure_inference_times(
            infer,
            [(1, dataset.test.X.sample(1, random_state=i)) for i in range(100)],
        )
        log.info("Finished inference time measurements.")

    with Timer() as predict:
        predictions = predictor.predict(X_test)[target_col]
    log.info(f"Finished predict in {predict.duration}s.")

    # Best-effort: reach into the generator's internal candidate list for
    # the real evaluated-pipeline count (same spirit as AutoGluon/exec.py's
    # predictor._trainer.model_best introspection -- not part of SapientML's
    # documented public API, so fall back to the configured n_models if it
    # isn't there).
    candidate_scripts = getattr(predictor.generator, "_candidate_scripts", None)
    models_count = len(candidate_scripts) if candidate_scripts else training_params.get(
        "n_models", 3
    )

    if is_classification:
        predictions = predictions.astype(str).str.lower().str.strip()
        truth = y_test.astype(str).str.lower().str.strip()

        classes = dataset.target.classes
        probabilities = OneHotEncoder(
            categories=[classes], handle_unknown="ignore"
        ).fit_transform(predictions.to_numpy().reshape(-1, 1))
        probabilities = pd.DataFrame(probabilities.toarray(), columns=classes)

        return result(
            output_file=config.output_predictions_file,
            predictions=predictions,
            truth=truth,
            probabilities=probabilities,
            probabilities_labels=classes,
            models_count=models_count,
            training_duration=training.duration,
            predict_duration=predict.duration,
            inference_times=inference_times,
            **feature_usage(all_columns),
        )
    else:
        return result(
            output_file=config.output_predictions_file,
            predictions=predictions,
            truth=y_test,
            models_count=models_count,
            training_duration=training.duration,
            predict_duration=predict.duration,
            inference_times=inference_times,
            **feature_usage(all_columns),
        )


if __name__ == "__main__":
    call_run(run)
