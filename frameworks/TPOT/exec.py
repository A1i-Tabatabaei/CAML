# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# NOT a near-verbatim port: AMLB's frameworks/TPOT/exec.py targets TPOT's
# pre-2025-rewrite API. Rewritten against the current TPOTClassifier/
# TPOTRegressor API, verified live against tpot 1.1.0's actual source
# (github.com/EpistasisLab/tpot), 2026-07-29 -- see framework.toml's
# gotchas for the full list of what changed and why. Everything not tied
# to the API break (metrics_mapping, the predict_proba try/except
# fallback, the inference-time measurement shape) is kept as AMLB had it.

import logging
import os
import tempfile as tmp

import pandas as pd
from numpy.random import default_rng
from tpot import TPOTClassifier, TPOTRegressor, __version__

from frameworks.shared.callee import (
    call_run,
    output_subdir,
    result,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage, used_columns_from_pipeline
from frameworks.shared.utils import Timer

os.environ["JOBLIB_TEMP_FOLDER"] = tmp.gettempdir()
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** TPOT [v{__version__}] ****\n")

    is_classification = config.type == "classification"
    metrics_mapping = dict(
        acc="accuracy",
        auc="roc_auc",
        f1="f1",
        logloss="neg_log_loss",
        mae="neg_mean_absolute_error",
        mse="neg_mean_squared_error",
        msle="neg_mean_squared_log_error",
        r2="r2",
        rmse="neg_mean_squared_error",  # TPOT scores on mse; CAML computes rmse independently on predictions
    )
    scoring_metric = (
        metrics_mapping[config.metric] if config.metric in metrics_mapping else None
    )
    if scoring_metric is None:
        raise ValueError(f"Performance metric {config.metric} not supported.")

    X_train, y_train = dataset.train.X, dataset.train.y.squeeze()

    training_params = {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    n_jobs = config.framework_params.get("_n_jobs", config.cores)
    search_space = config.framework_params.get("_search_space", "linear")

    log.info(
        "Running TPOT with a maximum time of %ss on %s cores, optimizing %s.",
        config.max_runtime_seconds,
        n_jobs,
        scoring_metric,
    )
    runtime_min = config.max_runtime_seconds / 60

    estimator = TPOTClassifier if is_classification else TPOTRegressor
    tpot = estimator(
        n_jobs=n_jobs,
        max_time_mins=runtime_min,
        scorers=[scoring_metric],
        scorers_weights=[1],
        search_space=search_space,
        random_state=config.seed,
        **training_params,
    )

    with Timer() as training:
        tpot.fit(X_train, y_train)
    log.info(f"Finished fit in {training.duration}s.")

    def infer(data):
        data = pd.read_parquet(data) if isinstance(data, str) else data
        if is_classification:
            try:
                return tpot.predict_proba(data)
            except (RuntimeError, AttributeError):
                return tpot.predict(data)
        return tpot.predict(data)

    inference_times = {}
    if config.measure_inference_time:
        log.info("TPOT inference time measurements exclude preprocessing time of CAML.")
        inference_times["file"] = measure_inference_times(
            infer, dataset.inference_subsample_files
        )
        inference_times["df"] = measure_inference_times(
            infer,
            [
                (1, dataset.test.X[default_rng(seed=i).integers(len(dataset.test.X)), :].reshape(1, -1))
                for i in range(100)
            ],
        )
        log.info("Finished inference time measurements.")

    log.info("Predicting on the test set.")
    y_test = dataset.test.y.squeeze()
    with Timer() as predict:
        X_test = dataset.test.X
        predictions = tpot.predict(X_test)
        if is_classification:
            # tpot.predict() returns its own internal integer-encoded
            # classes (e.g. 0/1), not the original string labels y_train
            # was fit with -- unlike FLAML/MLJAR/AutoGluon's underlying
            # libraries, which round-trip predict() in the same label
            # space as fit(). tpot.classes_ (standard sklearn attribute)
            # maps those codes back to the original labels, matching what
            # truth/predict_proba's columns are already in.
            predictions = tpot.classes_[predictions]

    try:
        probabilities = tpot.predict_proba(X_test) if is_classification else None
    except (RuntimeError, AttributeError):
        # tpot raises RuntimeError or AttributeError if the winning pipeline
        # doesn't support predict_proba -- encoding is handled by
        # __init__.py's process_results in that case.
        probabilities = "predictions"

    log.info(f"Finished predict in {predict.duration}s.")
    save_artifacts(tpot, config)

    # TPOT's search_space="linear" template includes real sklearn selectors
    # (SelectPercentile/SelectFwe/VarianceThreshold/RFE) as candidate pipeline
    # steps, so the winning pipeline may or may not have dropped columns --
    # see used_columns_from_pipeline()'s docstring for what shape is trusted.
    used_columns = used_columns_from_pipeline(tpot.fitted_pipeline_, X_train.columns)

    return result(
        output_file=config.output_predictions_file,
        predictions=predictions,
        truth=y_test,
        probabilities=probabilities,
        models_count=len(tpot.evaluated_individuals),
        training_duration=training.duration,
        predict_duration=predict.duration,
        inference_times=inference_times,
        **feature_usage(X_train.columns, used_columns),
    )


def save_artifacts(estimator, config):
    try:
        artifacts = config.framework_params.get("_save_artifacts", False)
        if "models" in artifacts:
            models_file = os.path.join(output_subdir("models", config), "evaluated_individuals.csv")
            estimator.evaluated_individuals.to_csv(models_file)
    except Exception:
        log.debug("Error when saving artifacts.", exc_info=True)


if __name__ == "__main__":
    call_run(run)
