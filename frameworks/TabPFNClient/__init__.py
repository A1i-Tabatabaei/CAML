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

    return run_in_venv(
        __file__,
        "exec.py",
        input_data=data,
        dataset=dataset,
        config=config,
        options=options,
        # Default retained_env_vars is just TMP/TEMP/TMPDIR -- TABPFN_TOKEN
        # needs to cross the subprocess boundary too, since tabpfn-client
        # reads it directly from the environment (see framework.toml).
        retained_env_vars=["TMP", "TEMP", "TMPDIR", "TABPFN_TOKEN"],
    )
