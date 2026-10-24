# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported from AMLB's frameworks/AutoGluon/__init__.py, tabular path only —
# the time-series branch (run_autogluon_timeseries / exec_ts.py) is dropped,
# CAML v1 has no time-series benchmark. Unlike FLAML/MLJAR (which pass X/y
# arrays), AutoGluon works on the raw dataframe with the target column
# included, so the splits are passed as parquet file paths plus the target
# feature — CAML's OpenML datasets expose exactly this via
# `dataset.<split>.data_path("parquet")` and `dataset.target`.


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(path=dataset.train.data_path("parquet")),
        test=dict(path=dataset.test.data_path("parquet")),
        target=dict(name=dataset.target.name, classes=dataset.target.values),
        problem_type=dataset.type.name,  # AutoGluon problem_type uses the same names as caml.data.DatasetType
    )
    if config.measure_inference_time:
        data["inference_subsample_files"] = dataset.inference_subsample_files(
            fmt="parquet"
        )

    return run_in_venv(
        __file__,
        "exec.py",
        input_data=data,
        dataset=dataset,
        config=config,
        # Forward the GPU knob across the subprocess boundary (default is just
        # TMP/TEMP/TMPDIR): CAML_COMPUTE=auto|cpu|gpu drives exec.py's
        # GPU auto-detection (frameworks/shared/compute.py). HOME is required on
        # a GPU box for the NVIDIA driver's JIT compile cache
        # ($HOME/.nv/ComputeCache) -- see the TabPFN __init__ for the full note.
        retained_env_vars=["TMP", "TEMP", "TMPDIR", "HOME", "CAML_COMPUTE"],
    )
