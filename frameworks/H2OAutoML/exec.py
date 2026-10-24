# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported from AMLB's frameworks/H2OAutoML/exec.py, trimmed of two things
# CAML doesn't need (see framework.toml's gotchas for why):
#   - the ARFF single/double-quote retry heuristic -- CAML's __init__.py
#     requests CSV explicitly via data_path("csv"), so the format-detection
#     dance AMLB needed for whatever raw format OpenML handed back doesn't
#     apply here. escapechar="\\" is kept (general CSV-escaping robustness,
#     not ARFF-specific).
#   - the opt-in BackendMemoryMonitoring hook -- config.ext.monitoring isn't
#     wired up anywhere in CAML (no other framework's exec.py ports it
#     either).
# The fit/predict/leaderboard core and the JVM cleanup in `finally` are
# otherwise unchanged from AMLB's implementation.

import logging
import os
import re

import pandas as pd

import h2o
from h2o.automl import H2OAutoML

from frameworks.shared.callee import (
    FrameworkError,
    call_run,
    output_subdir,
    result,
    measure_inference_times,
)
from frameworks.shared.feature_usage import feature_usage
from frameworks.shared.utils import Timer, Namespace as ns, touch

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** H2O AutoML [v{h2o.__version__}] ****\n")

    # Mapping of CAML/AMLB benchmark metrics to H2O's own metric names.
    metrics_mapping = dict(
        acc="mean_per_class_error",
        auc="AUC",
        logloss="logloss",
        mae="mae",
        mse="mse",
        r2="r2",
        rmse="rmse",
        rmsle="rmsle",
    )
    sort_metric = metrics_mapping.get(config.metric)
    if sort_metric is None:
        log.warning(
            "Performance metric %s not supported, defaulting to AUTO.", config.metric
        )

    try:
        training_params = {
            k: v for k, v in config.framework_params.items() if not k.startswith("_")
        }
        nthreads = config.framework_params.get("_nthreads", config.cores)
        jvm_memory = (
            str(round(config.max_mem_size_mb * 2 / 3)) + "M"
        )  # leave 1/3rd of available memory for XGBoost, matching AMLB

        log.info(
            "Starting H2O cluster with %s cores, %s memory.", nthreads, jvm_memory
        )
        # Randomize the port per-job (still deterministic per pid) so that
        # back-to-back H2O jobs on the same box never race for the same port
        # if a prior JVM is slow to release it.
        max_port_range = 49151
        min_port_range = 1024
        rnd_port = os.getpid() % (max_port_range - min_port_range) + min_port_range
        port = config.framework_params.get("_port", rnd_port)
        init_params = config.framework_params.get("_init", {})

        h2o.init(
            nthreads=nthreads,
            port=port,
            min_mem_size=jvm_memory,
            max_mem_size=jvm_memory,
            **init_params,
        )

        import_kwargs = dict(escapechar="\\")
        log.debug("Loading train data from %s.", dataset.train.path)
        train = h2o.import_file(
            dataset.train.path,
            destination_frame=frame_name("train", config),
            **import_kwargs,
        )
        log.debug("Loading test data from %s.", dataset.test.path)
        test = h2o.import_file(
            dataset.test.path,
            destination_frame=frame_name("test", config),
            **import_kwargs,
        )

        if config.type == "classification":
            train[dataset.target.index] = train[dataset.target.index].asfactor()
            test[dataset.target.index] = test[dataset.target.index].asfactor()

        log.info("Running model on task %s, fold %s.", config.name, config.fold)
        log.debug(
            "Running H2O AutoML with a maximum time of %ss on %s core(s), optimizing %s.",
            config.max_runtime_seconds,
            config.cores,
            sort_metric,
        )

        aml = H2OAutoML(
            max_runtime_secs=config.max_runtime_seconds,
            sort_metric=sort_metric,
            seed=config.seed,
            **training_params,
        )

        with Timer() as training:
            aml.train(y=dataset.target.index, training_frame=train)
        log.info(f"Finished fit in {training.duration}s.")

        if not aml.leader:
            raise FrameworkError(
                "H2O could not produce any model in the requested time."
            )

        def infer(path: str):
            import pathlib

            filename = pathlib.Path(path).name
            # H2O can't infer on a single-row file without explicit column
            # names: https://github.com/h2oai/h2o-3/issues/15572
            batch = h2o.import_file(
                path,
                col_names=train.names,
                destination_frame=frame_name(filename, config),
                **import_kwargs,
            )
            return aml.predict(batch)

        inference_times = {}
        if config.measure_inference_time:
            inference_times["file"] = measure_inference_times(
                infer, dataset.inference_subsample_files
            )
            log.info("Finished inference time measurements.")

        with Timer() as predict:
            preds = aml.predict(test)
        log.info(f"Finished predict in {predict.duration}s.")

        preds = extract_preds(preds, test, dataset=dataset)
        save_artifacts(aml, config)

        target_name = train.names[dataset.target.index]
        all_columns = [c for c in train.names if c != target_name]

        return result(
            output_file=config.output_predictions_file,
            predictions=preds.predictions,
            truth=preds.truth,
            probabilities=preds.probabilities,
            probabilities_labels=preds.probabilities_labels,
            models_count=len(aml.leaderboard),
            training_duration=training.duration,
            predict_duration=predict.duration,
            inference_times=inference_times,
            **feature_usage(all_columns),
        )

    finally:
        # Guard against orphaned `java` processes on any exit path
        # (success, exception, or a job-timeout interrupt from callee.py's
        # InterruptTimeout, which still runs this `finally` block).
        con = h2o.connection()
        if con:
            con.close()
            if con.local_server:
                con.local_server.shutdown()


def frame_name(fr_type, config):
    return "_".join([fr_type, config.name, str(config.fold)])


def save_artifacts(automl, config):
    try:
        artifacts = config.framework_params.get("_save_artifacts", False)
        if "leaderboard" in artifacts:
            lb = automl.leaderboard.as_data_frame()
            log.debug("Leaderboard:\n%s", lb.to_string())
            lb_path = os.path.join(
                output_subdir("leaderboard", config), "leaderboard.csv"
            )
            touch(lb_path)
            lb.to_csv(lb_path, header=True, index=False)
    except Exception:
        log.debug("Error when saving artifacts.", exc_info=True)


def extract_preds(h2o_preds, test, dataset):
    h2o_preds = h2o_preds.as_data_frame(use_pandas=False)
    preds = pd.DataFrame.from_records(h2o_preds[1:], columns=h2o_preds[0])
    y_pred = preds.iloc[:, 0]

    h2o_truth = test[:, dataset.target.index].as_data_frame(
        use_pandas=False, header=False
    )
    y_truth = pd.DataFrame.from_records(h2o_truth)

    predictions = y_pred.values
    probabilities = preds.iloc[:, 1:].values
    prob_labels = h2o_preds[0][1:]
    if all(re.fullmatch(r"p(-?\d)+", p) for p in prob_labels):
        # For categories represented as numerical values, h2o prefixes the
        # probability columns with "p" -- in this case let the app assign
        # labels itself to avoid a mismatch.
        prob_labels = None
    truth = y_truth.values

    return ns(
        predictions=predictions,
        truth=truth,
        probabilities=probabilities,
        probabilities_labels=prob_labels,
    )


if __name__ == "__main__":
    call_run(run)
