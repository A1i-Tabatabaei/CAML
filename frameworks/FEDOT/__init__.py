# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# AMLB's own FEDOT/__init__.py branches on dataset.type to dispatch to a
# separate time-series exec_ts.py path -- out of scope here (CAML's v1
# roster is tabular classification/regression only, see STATUS.md), so
# only the tabular path (AMLB's run_fedot_tabular) is ported. Data dict
# shape follows CAML's own array-based convention (same as TPOT/
# NaiveAutoML), plus the measure_inference_time wiring AMLB's own FEDOT
# integration predates.


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(X=dataset.train.X, y=dataset.train.y),
        test=dict(X=dataset.test.X, y=dataset.test.y),
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
