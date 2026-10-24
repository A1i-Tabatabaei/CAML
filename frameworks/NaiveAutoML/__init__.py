# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported from AMLB's frameworks/NaiveAutoML/__init__.py, minus the unused
# `target=dataset.target.name` field (exec.py never reads it).


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(X=dataset.train.X, y=dataset.train.y_enc),
        test=dict(X=dataset.test.X, y=dataset.test.y_enc),
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
    )
