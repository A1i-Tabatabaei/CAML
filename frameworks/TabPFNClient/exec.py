# Pivoted from the local `tabpfn` package (blocked on a Prior Labs
# license/weight-download gate -- see STATUS.md's "Blocked" history) to
# Prior Labs' hosted `tabpfn-client`, 2026-07-30, at the user's direction
# after creating a Prior Labs account + API key. TabPFNClassifier/
# TabPFNRegressor here are thin REST/SSE clients -- .fit()/.predict()/
# .predict_proba() send data to Prior Labs' servers and get results back.
# No local model, no device/n_jobs kwargs (both were specific to the old
# local package's in-process inference), nothing to pre-warm at install
# time. See framework.toml's gotchas for the external-data-transmission
# and rate-limit implications.
#
# Still architecturally different from every other framework here: TabPFN
# does in-context inference over the training set in one forward pass, not
# a hyperparameter search, so there's no time budget to spend by default --
# config.max_runtime_seconds is unused unless a caller opts into
# tabpfn-client's "thinking mode" via framework_params, which flows through
# the standard **training_params passthrough below.

import logging
import os
from importlib.metadata import version as pkg_version

import pandas as pd
from tabpfn_client import TabPFNClassifier, TabPFNRegressor

from frameworks.shared.callee import (
    FrameworkError,
    call_run,
    result,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)

# Committed to the repo as an obviously-fake value (see
# docs/operations/tabpfn-access.md) so that anyone who hasn't set a real
# TABPFN_TOKEN gets a clear, actionable error instead of a confusing
# auth failure from deep inside tabpfn-client.
_TOKEN_PLACEHOLDER = "REPLACE_WITH_YOUR_TABPFN_API_KEY"


def run(dataset, config):
    log.info(
        f"\n**** TabPFNClient [tabpfn-client v{pkg_version('tabpfn-client')}] ****\n"
    )

    token = os.environ.get("TABPFN_TOKEN")
    if not token or token == _TOKEN_PLACEHOLDER:
        raise FrameworkError(
            "TABPFN_TOKEN is not set (or is still the placeholder value). "
            "Register at https://ux.priorlabs.ai, accept the license, copy "
            "an API key, and set TABPFN_TOKEN in the environment before "
            "running this framework -- see docs/operations/tabpfn-access.md."
        )

    X_train, y_train = dataset.train.X, dataset.train.y.squeeze()
    X_test, y_test = dataset.test.X, dataset.test.y.squeeze()

    is_classification = config.type == "classification"
    estimator_cls = TabPFNClassifier if is_classification else TabPFNRegressor

    training_params = {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    model = estimator_cls(random_state=config.seed, **training_params)

    with Timer() as training:
        model.fit(X_train, y_train)
    log.info(f"Finished fit in {training.duration}s.")

    def infer(data):
        data = pd.read_parquet(data) if isinstance(data, str) else data
        predict_fn = model.predict_proba if is_classification else model.predict
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
        predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test) if is_classification else None
    labels = None
    if is_classification:
        labels = (
            model.classes_.tolist()
            if hasattr(model.classes_, "tolist")
            else list(model.classes_)
        )
    log.info(f"Finished predict in {predict.duration}s.")

    return result(
        output_file=config.output_predictions_file,
        probabilities=probabilities,
        predictions=predictions,
        truth=y_test,
        models_count=1,
        training_duration=training.duration,
        predict_duration=predict.duration,
        probabilities_labels=labels,
        inference_times=inference_times,
        **feature_usage(X_train.columns),
    )


if __name__ == "__main__":
    call_run(run)
