# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported from AMLB's frameworks/lightautoml/__init__.py. Unlike FLAML/MLJAR
# (X/y arrays) or AutoGluon/H2O (file paths), LightAutoML's train split is
# the *full* dataframe (predictors + target) via dataset.train.data --
# TabularUtilizedAutoML.fit_predict() takes roles={"target": <name>} and
# expects the target column embedded in train_data. Test data stays X/y
# split since prediction only needs predictors.


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(data=dataset.train.data),
        test=dict(X=dataset.test.X, y=dataset.test.y),
        target=dict(name=dataset.target.name),
        problem_type=dataset.type.name,
    )
    if config.measure_inference_time:
        data["inference_subsample_files"] = dataset.inference_subsample_files(
            fmt="parquet"
        )
    options = dict(serialization=dict(sparse_dataframe_deserialized_format="dense"))

    return run_in_venv(
        __file__,
        "exec.py",
        input_data=data,
        dataset=dataset,
        config=config,
        options=options,
        # Forward the GPU knobs across the subprocess boundary (default is just
        # TMP/TEMP/TMPDIR): CAML_COMPUTE=auto|cpu|gpu drives exec.py's device
        # auto-detection, CAML_GPU_IDS overrides which CUDA device(s) to use.
        # HOME is required on a GPU box for the NVIDIA driver's JIT compile
        # cache ($HOME/.nv/ComputeCache) -- see the TabPFN __init__ for the note.
        retained_env_vars=["TMP", "TEMP", "TMPDIR", "HOME", "CAML_COMPUTE", "CAML_GPU_IDS"],
    )
