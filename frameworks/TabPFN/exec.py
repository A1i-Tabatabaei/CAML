# Local TabPFN: runs the TabPFN foundation model on-box via the OSS `tabpfn`
# package. TabPFNClassifier/TabPFNRegressor here are real, local sklearn-style
# estimators -- .fit()/.predict()/.predict_proba() run inference in-process,
# nothing goes over the network. The only network access is a one-time,
# license-gated download of the model weights on first use (cached under
# ~/.cache/tabpfn, or TABPFN_MODEL_CACHE_DIR), authenticated via TABPFN_TOKEN.
#
# This is the deliberate counterpart to `frameworks/TabPFNClient/exec.py`
# (the hosted-API variant, where every fit/predict ships data to Prior Labs'
# servers). Same result() contract, same array-based data flow; the deltas are
# the package (`tabpfn` vs `tabpfn-client`, plus a real torch dependency) and
# the `device` kwarg (which the client's server-side estimators don't have).
#
# Still architecturally different from the search-based frameworks in the
# roster: TabPFN does in-context inference in a single forward pass, not a
# hyperparameter search, so there's no time budget to spend by default --
# config.max_runtime_seconds is unused unless a caller opts into extra fit-time
# compute via framework_params, which flows through the **training_params
# passthrough below.

import logging
import os
from importlib.metadata import version as pkg_version

import pandas as pd
from tabpfn import TabPFNClassifier, TabPFNRegressor

from frameworks.shared.callee import (
    FrameworkError,
    call_run,
    result,
    measure_inference_times,
)
from frameworks.shared.compute import torch_device, describe as describe_compute
from frameworks.shared.feature_usage import feature_usage
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)

# Committed to the repo as an obviously-fake value (see
# docs/operations/tabpfn-access.md) so that anyone who hasn't set a real
# TABPFN_TOKEN gets a clear, actionable error instead of a confusing failure
# from deep inside tabpfn's weight-download/license handshake.
_TOKEN_PLACEHOLDER = "REPLACE_WITH_YOUR_TABPFN_API_KEY"


def run(dataset, config):
    log.info(
        f"\n**** TabPFN (local) [tabpfn v{pkg_version('tabpfn')}] "
        f"on {describe_compute()} ****\n"
    )

    # The token is needed for the *one-time* weight download (not every call,
    # unlike the hosted client). Once weights are cached, inference is fully
    # local. We still fail fast on a missing token so a first-run setup gap
    # surfaces as a clear message rather than a browser-login attempt or auth
    # error on a headless box.
    token = os.environ.get("TABPFN_TOKEN")
    if not token or token == _TOKEN_PLACEHOLDER:
        raise FrameworkError(
            "TABPFN_TOKEN is not set (or is still the placeholder value). "
            "The local `tabpfn` package needs it once to download the model "
            "weights: register at https://ux.priorlabs.ai, accept the license, "
            "copy an API key, and set TABPFN_TOKEN in the environment before "
            "running this framework -- see docs/operations/tabpfn-access.md. "
            "(Only the first run needs network access; weights are cached "
            "afterwards.)"
        )

    X_train, y_train = dataset.train.X, dataset.train.y.squeeze()
    X_test, y_test = dataset.test.X, dataset.test.y.squeeze()

    is_classification = config.type == "classification"
    estimator_cls = TabPFNClassifier if is_classification else TabPFNRegressor

    training_params = {
        k: v for k, v in config.framework_params.items() if not k.startswith("_")
    }
    # GPU by default (Phase 8): use CUDA when a usable GPU is present, CPU
    # otherwise -- resolved by frameworks/shared/compute.py, overridable per
    # box via CAML_COMPUTE and per run via framework_params["device"]. TabPFN
    # is the prime GPU beneficiary in this roster: besides the raw speedup,
    # running on CUDA also lifts TabPFN-3's default >1000-sample refusal that
    # caps the CPU path (see docs/frameworks/tabpfn.md), so large validation
    # tasks that fail on CPU succeed on GPU with no other change.
    training_params.setdefault("device", torch_device())
    log.info("Using device=%s for TabPFN inference.", training_params["device"])
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
