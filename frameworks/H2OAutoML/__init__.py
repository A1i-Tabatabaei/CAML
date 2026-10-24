# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Ported from AMLB's frameworks/H2OAutoML/__init__.py, minus the
# `domains=dict(cardinalities=...)` field: that existed solely to support
# exec.py's ARFF single/double-quote retry heuristic, which CAML doesn't
# need (see framework.toml's gotchas -- CSV format is requested explicitly).


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(path=dataset.train.data_path("csv")),
        test=dict(path=dataset.test.data_path("csv")),
        target=dict(index=dataset.target.index),
    )
    if config.measure_inference_time:
        data["inference_subsample_files"] = dataset.inference_subsample_files(
            fmt="csv", with_labels=True
        )

    return run_in_venv(
        __file__, "exec.py", input_data=data, dataset=dataset, config=config
    )
