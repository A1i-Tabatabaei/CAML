# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# AMLB's own SapientML/__init__.py (both the generic openml/automlbenchmark
# copy and the SapientML team's own fork) reads dataset.train.path/
# dataset.test.path as raw CSVs -- CAML's own dataset.*.path defaults to
# parquet (confirmed via AutoGluon/exec.py's pd.read_parquet(dataset.test.path)
# usage), which SapientML's own file-path loader doesn't understand (only
# .pkl, or falls through to pd.read_csv). Uses dataset.train.data (the full
# predictors+target dataframe) instead, same pattern as
# frameworks/LightAutoML/__init__.py -- SapientML.fit() accepts a DataFrame
# directly, no file round-trip needed. See docs/frameworks/sapientml.md
# Part 2 for the full reasoning.


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(data=dataset.train.data),
        test=dict(X=dataset.test.X, y=dataset.test.y),
        target=dict(name=dataset.target.name, classes=dataset.target.values),
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
    )
