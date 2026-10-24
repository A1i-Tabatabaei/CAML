# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported near-verbatim from AMLB's frameworks/lightautoml/exec.py, confirmed
# against lightautoml 0.4.2 (2026-07-30): TabularUtilizedAutoML's
# constructor, Task's valid name strings, and the reader.class_mapping
# attribute this file reaches into for label recovery are all unchanged --
# see framework.toml's gotchas for what was actually verified live.

import logging
import os
import pickle
import warnings
from typing import Union

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("agg")  # no need for tk

from lightautoml.tasks import Task
from lightautoml.automl.presets.tabular_presets import TabularUtilizedAutoML
from lightautoml import __version__

from frameworks.shared.callee import (
    call_run,
    result,
    output_subdir,
    measure_inference_times,
)
from frameworks.shared.compute import use_gpu, describe as describe_compute
from frameworks.shared.feature_usage import feature_usage, union_of_branch_features
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** LightAutoML [v{__version__}] on {describe_compute()} ****\n")

    warnings.simplefilter(action="ignore", category=FutureWarning)
    warnings.simplefilter(action="ignore", category=DeprecationWarning)

    is_classification = config.type == "classification"

    label = dataset.target.name
    df_train = dataset.train.data

    max_mem_size_gb = float(config.max_mem_size_mb) / 1024
    task = Task(dataset.problem_type if dataset.problem_type != "regression" else "reg")
    automl_kwargs = dict(
        task=task,
        timeout=config.max_runtime_seconds,
        cpu_limit=config.cores,
        memory_limit=max_mem_size_gb,
        random_state=config.seed,
    )
    # GPU by default (Phase 8): LightAutoML exposes `gpu_ids` on
    # TabularUtilizedAutoML (confirmed live). "0" selects the first CUDA
    # device; overridable via CAML_GPU_IDS (e.g. "0,1" / "all") or forced off
    # with CAML_COMPUTE=cpu. Its GPU pipelines are optional/heavier than the
    # CPU ones -- see framework.toml gotchas + docs/operations/gpu.md.
    if use_gpu():
        automl_kwargs["gpu_ids"] = os.environ.get("CAML_GPU_IDS", "0")
        log.info("GPU detected; passing gpu_ids=%s to LightAutoML.", automl_kwargs["gpu_ids"])
    automl = TabularUtilizedAutoML(**automl_kwargs)

    log.info("Training...")
    with Timer() as training:
        automl.fit_predict(train_data=df_train, roles={"target": label})
    log.info(f"Finished fit in {training.duration}s.")

    def infer(data: Union[str, pd.DataFrame]):
        batch = pd.read_parquet(data) if isinstance(data, str) else data
        return automl.predict(batch)

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

    log.info("Predicting on the test set...")
    with Timer() as predict:
        X_test = dataset.test.X
        preds = automl.predict(X_test).data

    probabilities_labels = None
    if is_classification:
        probabilities = preds

        if dataset.problem_type == "binary":
            probabilities = np.vstack([1 - probabilities[:, 0], probabilities[:, 0]]).T

        predictions = np.argmax(probabilities, axis=1)
        class_map = automl.outer_pipes[0].ml_algos[0].models[0][0].reader.class_mapping
        if class_map is None and df_train[label].dtype == bool:
            class_map = {False: 0, True: 1}
        if class_map:
            column_to_class = {col: class_ for class_, col in class_map.items()}
            predictions = list(map(column_to_class.get, predictions))
            probabilities_labels = [
                column_to_class[col] for col in sorted(column_to_class)
            ]
    else:
        probabilities = None
        predictions = preds

    log.info(f"Finished predict in {predict.duration}s.")

    save_artifacts(automl, config)

    all_columns = [c for c in df_train.columns if c != label]
    try:
        used_columns = union_of_branch_features(
            _lightautoml_leaf_models(automl), attr="collect_used_feats"
        )
    except Exception:
        log.warning(
            "LightAutoML feature-usage introspection failed; reporting all "
            "columns as used.",
            exc_info=True,
        )
        used_columns = None

    return result(
        output_file=config.output_predictions_file,
        probabilities_labels=probabilities_labels,
        probabilities=probabilities,
        predictions=predictions,
        training_duration=training.duration,
        predict_duration=predict.duration,
        inference_times=inference_times,
        **feature_usage(all_columns, used_columns),
    )


def _lightautoml_leaf_models(automl):
    """Walk automl.outer_pipes[*].ml_algos[*].models[*][*] -- the SAME object
    graph this file already reaches into above for `.reader.class_mapping`.
    Confirmed live 2026-09-10 (lightautoml 0.4.2): each leaf is a
    `TabularAutoML` instance (wrapped via `MLAlgoForAutoMLWrapper`), not a
    raw model -- it exposes a real public method, `collect_used_feats()`
    (returns `List[str]`, already unioned across that inner AutoML's own
    levels/pipes), which `union_of_branch_features(..., attr=
    "collect_used_feats")` calls per leaf. Traversing outer_pipes/ml_algos
    itself is still not part of LightAutoML's documented public API;
    TabularUtilizedAutoML blends several inner TabularAutoML runs, so this
    is a best-effort union across whatever branches are reachable -- see
    union_of_branch_features()'s docstring for the conservative fallback
    when a branch isn't.
    """
    for pipe in getattr(automl, "outer_pipes", None) or []:
        for ml_algo in getattr(pipe, "ml_algos", None) or []:
            for fold_models in getattr(ml_algo, "models", None) or []:
                yield from (fold_models or [])


def save_artifacts(automl, config):
    try:
        artifacts = config.framework_params.get("_save_artifacts", [])
        if "models" in artifacts:
            models_dir = output_subdir("models", config)
            with open(os.path.join(models_dir, "automl.pickle"), "wb") as f:
                pickle.dump(automl, f)
    except Exception:
        log.warning("Error when saving artifacts.", exc_info=True)


if __name__ == "__main__":
    call_run(run)
