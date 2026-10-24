# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# NOT a verbatim port: AMLB's exec.py passes `timeout=`/`execution_timeout=`
# to the NaiveAutoML constructor, neither of which exists in the current
# source (confirmed live against github.com/fmohr/naiveautoml,
# 2026-07-30). The real kwargs are `timeout_overall`/`timeout_candidate` --
# see framework.toml's gotchas for the full diff. AMLB's derivation logic
# (per-candidate timeout scaled from the overall budget) is kept, just
# under the corrected parameter name. Version detection uses
# importlib.metadata instead of AMLB's `pip list` subprocess-parsing
# workaround (naiveautoml doesn't expose its own __version__ attribute --
# github.com/fmohr/naiveautoml/issues/22 -- but importlib.metadata reads
# the installed distribution's metadata directly, independent of that).

import logging
import os
from importlib.metadata import version as pkg_version

import pandas as pd
from naiveautoml import NaiveAutoML

from frameworks.shared.callee import (
    call_run,
    output_subdir,
    result,
    measure_inference_times,
)
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** NaiveAutoML [v{pkg_version('naiveautoml')}] ****\n")

    metrics_mapping = dict(
        acc="accuracy",
        balacc="balanced_accuracy",
        auc="roc_auc",
        logloss="neg_log_loss",
        mae="neg_mean_absolute_error",
        r2="r2",
        rmse="neg_mean_squared_error",
    )
    scoring_metric = metrics_mapping.get(config.metric)
    if scoring_metric is None:
        raise ValueError(f"Performance metric {config.metric} not supported.")

    kwargs = dict(scoring=scoring_metric, num_cpus=config.cores)
    # NaiveAutoML wasn't designed around a hard time budget; give callers an
    # escape hatch to run it with its own defaults instead (matching AMLB).
    if not config.framework_params.get("_use_default_time_and_iterations", False):
        kwargs["timeout_overall"] = config.max_runtime_seconds
        # NaiveAutoML stops at whichever of {iterations, time} it hits
        # first -- set iterations very high so time is always the binding
        # constraint.
        # int, not AMLB's 1e10 float: current naiveautoml does
        # `range(self.task.max_hpo_iterations)` internally (confirmed live,
        # 2026-07-30), which raises TypeError on a float. A real behavior
        # difference from whatever version AMLB last verified against.
        kwargs["max_hpo_iterations"] = 10_000_000_000
        # Per-candidate-pipeline timeout doesn't scale with dataset size on
        # its own; derive it from the overall budget instead (AMLB's logic,
        # ported under the current parameter name -- see framework.toml).
        kwargs["timeout_candidate"] = max(config.max_runtime_seconds // 20, 10)
    else:
        log.info("`_use_default_time_and_iterations` is set, ignoring time constraint.")

    kwargs |= {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    automl = NaiveAutoML(**kwargs)

    with Timer() as training:
        automl.fit(dataset.train.X, dataset.train.y)
    log.info(f"Finished fit in {training.duration}s.")

    is_classification = config.type == "classification"

    def infer(data):
        data = pd.read_parquet(data) if isinstance(data, str) else data
        predict_fn = automl.predict_proba if is_classification else automl.predict
        return predict_fn(data)

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
        predictions = automl.predict(dataset.test.X)
        probabilities = (
            automl.predict_proba(dataset.test.X) if is_classification else None
        )
    log.info(f"Finished predict in {predict.duration}s.")

    save_artifacts(automl, config)

    return result(
        output_file=config.output_predictions_file,
        predictions=predictions,
        probabilities=probabilities,
        training_duration=training.duration,
        predict_duration=predict.duration,
        inference_times=inference_times,
        target_is_encoded=is_classification,
    )


def save_artifacts(naive_automl, config):
    try:
        artifacts = config.framework_params.get("_save_artifacts", ["history"])
        if "history" in artifacts:
            artifacts_dir = output_subdir("artifacts", config)
            naive_automl.history.to_csv(
                os.path.join(artifacts_dir, "history.csv"), index=False
            )
    except Exception:
        log.debug("Error when saving artifacts.", exc_info=True)


if __name__ == "__main__":
    call_run(run)
