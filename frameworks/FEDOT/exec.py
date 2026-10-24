# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Near-verbatim port -- verified live against fedot 0.7.5's actual source
# (github.com/aimclub/FEDOT), 2026-07-30: unlike TPOT/NaiveAutoML, no
# breaking API drift found (see framework.toml's gotchas for what was
# checked and why it mattered). The one real addition beyond the AMLB
# reference is the measure_inference_time wiring (same pattern as TPOT/
# LightAutoML), which AMLB's own FEDOT/exec.py predates.

import logging
import os
from pathlib import Path

import pandas as pd
from numpy.random import default_rng

from fedot import __version__
from fedot.api.main import Fedot

from frameworks.shared.callee import (
    call_run,
    output_subdir,
    result,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** FEDOT [v{__version__}] ****\n")

    is_classification = config.type == "classification"
    scoring_metric = get_fedot_metrics(config)

    training_params = {"preset": "best_quality", "n_jobs": config.cores}
    training_params.update(
        {k: v for k, v in config.framework_params.items() if not k.startswith("_")}
    )
    n_jobs = training_params["n_jobs"]

    log.info(
        "Running FEDOT with a maximum time of %ss on %s cores, optimizing %s.",
        config.max_runtime_seconds,
        n_jobs,
        scoring_metric,
    )

    runtime_min = config.max_runtime_seconds / 60

    fedot = Fedot(
        problem=config.type,
        timeout=runtime_min,
        metric=scoring_metric,
        seed=config.seed,
        max_pipeline_fit_time=runtime_min / 10,
        **training_params,
    )

    with Timer() as training:
        fedot.fit(features=dataset.train.X, target=dataset.train.y)
    log.info(f"Finished fit in {training.duration}s.")

    def infer(data):
        data = pd.read_parquet(data) if isinstance(data, str) else data
        return (
            fedot.predict_proba(data, probs_for_all_classes=True)
            if is_classification
            else fedot.predict(data)
        )

    inference_times = {}
    if config.measure_inference_time:
        log.info(
            "FEDOT inference time measurements exclude preprocessing time of CAML."
        )
        inference_times["file"] = measure_inference_times(
            infer, dataset.inference_subsample_files
        )
        inference_times["df"] = measure_inference_times(
            infer,
            [
                (
                    1,
                    dataset.test.X[
                        default_rng(seed=i).integers(len(dataset.test.X)), :
                    ].reshape(1, -1),
                )
                for i in range(100)
            ],
        )
        log.info("Finished inference time measurements.")

    log.info("Predicting on the test set.")
    with Timer() as predict:
        predictions = fedot.predict(features=dataset.test.X)
    probabilities = None
    if is_classification:
        probabilities = fedot.predict_proba(
            features=dataset.test.X, probs_for_all_classes=True
        )
    log.info(f"Finished predict in {predict.duration}s.")

    save_artifacts(fedot, config)

    return result(
        output_file=config.output_predictions_file,
        predictions=predictions,
        truth=dataset.test.y,
        probabilities=probabilities,
        target_is_encoded=False,
        models_count=fedot.current_pipeline.length,
        training_duration=training.duration,
        predict_duration=predict.duration,
        inference_times=inference_times,
        **feature_usage(dataset.train.X.columns),
    )


def get_fedot_metrics(config):
    metrics_mapping = dict(
        acc="accuracy",
        auc="roc_auc",
        f1="f1",
        logloss="neg_log_loss",
        mae="mae",
        mse="mse",
        msle="msle",
        r2="r2",
        rmse="rmse",
    )
    scoring_metric = metrics_mapping.get(config.metric, None)

    if scoring_metric is None:
        log.warning(f"Performance metric {config.metric} not supported.")

    return scoring_metric


def save_artifacts(automl, config):
    artifacts = config.framework_params.get("_save_artifacts", [])
    if "models" in artifacts:
        try:
            models_dir = output_subdir("models", config)
            models_file = os.path.join(models_dir, "model.json")
            automl.current_pipeline.save(models_file)
        except Exception as e:
            log.info(f"Error when saving 'models': {e}.", exc_info=True)

    if "info" in artifacts:
        try:
            info_dir = output_subdir("info", config)
            if automl.history:
                automl.history.save(os.path.join(info_dir, "history.json"))
            else:
                log.info("There is no optimization history info to save.")
        except Exception as e:
            log.info(
                f"Error when saving info about optimisation history: {e}.",
                exc_info=True,
            )

    if "leaderboard" in artifacts:
        try:
            leaderboard_dir = output_subdir("leaderboard", config)
            if automl.history:
                lb = automl.history.get_leaderboard()
                Path(os.path.join(leaderboard_dir, "leaderboard.csv")).write_text(lb)
        except Exception as e:
            log.info(f"Error when saving 'leaderboard': {e}.", exc_info=True)


if __name__ == "__main__":
    call_run(run)
