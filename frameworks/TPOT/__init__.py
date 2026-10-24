# Portions of this file (the process_results predict_proba-fallback
# handling) are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Data dict shape follows CAML's own array-based convention (same as
# FLAML/MLJAR), not AMLB's TPOT-specific X_enc/y_enc/unsparsify handling --
# CAML's dataset.train.X/.y already normalize that.


def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(X=dataset.train.X, y=dataset.train.y),
        test=dict(X=dataset.test.X, y=dataset.test.y),
        problem_type=dataset.type.name,
    )
    if config.measure_inference_time:
        data["inference_subsample_files"] = dataset.inference_subsample_files(
            fmt="parquet"
        )
    options = dict(serialization=dict(sparse_dataframe_deserialized_format="dense"))

    def process_results(results):
        if (
            isinstance(results.probabilities, str)
            and results.probabilities == "predictions"
        ):
            from caml.datautils import Encoder

            target_values_enc = dataset.target.label_encoder.transform(
                dataset.target.values
            )
            results.probabilities = (
                Encoder("one-hot", target=False, encoded_type=float)
                .fit(target_values_enc)
                .transform(results.predictions)
            )
        return results

    return run_in_venv(
        __file__,
        "exec.py",
        input_data=data,
        dataset=dataset,
        config=config,
        options=options,
        process_results=process_results,
    )
