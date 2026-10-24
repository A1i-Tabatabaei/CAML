# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Near-verbatim port -- verified live against gama 23.0.0.post1's actual
# source (github.com/amore-labs/gama), 2026-07-30: Gama.__init__'s
# n_jobs/max_total_time/scoring/random_state/max_memory_mb/
# output_directory kwargs, .fit()/.predict()/.predict_proba(), and the
# private _final_pop attribute are all unchanged -- see framework.toml's
# gotchas for what was checked. AMLB's reference has a version_leq_20_2_0
# branch for a GAMA API predating 20.2.0 -- dropped as dead code, CAML's
# exact-pin-and-deliberately-bump policy will never install anything that
# old.

import logging
import os
import tempfile as tmp
from typing import Union

import pandas as pd

os.environ["JOBLIB_TEMP_FOLDER"] = tmp.gettempdir()
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from gama import GamaClassifier, GamaRegressor, __version__

from frameworks.shared.callee import (
    call_run,
    result,
    output_subdir,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage, used_columns_from_pipeline
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** GAMA [v{__version__}] ****\n")

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
        rmse="neg_mean_squared_error",
    )
    scoring_metric = (
        metrics_mapping[config.metric] if config.metric in metrics_mapping else None
    )
    if scoring_metric is None:
        raise ValueError(f"Performance metric {config.metric} not supported.")

    training_params = {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    n_jobs = config.framework_params.get("_n_jobs", config.cores)

    log.info(
        "Running GAMA with a maximum time of %ss on %s cores, optimizing %s.",
        config.max_runtime_seconds,
        n_jobs,
        scoring_metric,
    )

    estimator = GamaClassifier if is_classification else GamaRegressor
    gama_automl = estimator(
        n_jobs=n_jobs,
        max_total_time=config.max_runtime_seconds,
        scoring=scoring_metric,
        random_state=config.seed,
        max_memory_mb=config.max_mem_size_mb,
        output_directory=output_subdir("logs", config),
        **training_params,
    )

    X_train, y_train = dataset.train.X, dataset.train.y
    with Timer() as training:
        gama_automl.fit(X_train, y_train)
    log.info(f"Finished fit in {training.duration}s.")

    log.info("Predicting on the test set.")

    def infer(data: Union[str, pd.DataFrame]):
        test_data = pd.read_parquet(data) if isinstance(data, str) else data
        predict_fn = (
            gama_automl.predict_proba if is_classification else gama_automl.predict
        )
        return predict_fn(test_data)

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
        X_test, y_test = dataset.test.X, dataset.test.y
        predictions = gama_automl.predict(X_test)
    log.info(f"Finished predict in {predict.duration}s.")

    probabilities = None
    if is_classification:
        probabilities = gama_automl.predict_proba(X_test)

    # GAMA's default search space always includes SelectFwe/SelectPercentile/
    # VarianceThreshold as candidate pipeline steps (not opt-in), so the
    # winning pipeline (gama_automl.model) may or may not have dropped
    # columns -- see used_columns_from_pipeline()'s docstring for what shape
    # is trusted. getattr(..., None) so an unexpected attribute name degrades
    # to "all columns used" rather than crashing the run.
    used_columns = used_columns_from_pipeline(
        getattr(gama_automl, "model", None), X_train.columns
    )

    return result(
        output_file=config.output_predictions_file,
        predictions=predictions,
        probabilities=probabilities,
        truth=y_test,
        target_is_encoded=False,
        models_count=len(gama_automl._final_pop),
        training_duration=training.duration,
        predict_duration=predict.duration,
        inference_times=inference_times,
        **feature_usage(X_train.columns, used_columns),
    )


if __name__ == "__main__":
    call_run(run)
