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
        # Default retained_env_vars is just TMP/TEMP/TMPDIR. The local `tabpfn`
        # package reads TABPFN_TOKEN from the environment for its one-time
        # weight download, and honors TABPFN_MODEL_CACHE_DIR for where those
        # weights are cached -- both need to cross the subprocess boundary.
        # CAML_COMPUTE (auto|cpu|gpu) lets exec.py's device auto-detection be
        # overridden per box (frameworks/shared/compute.py).
        # HOME is required on a GPU box: the NVIDIA driver locates its JIT
        # compile cache at $HOME/.nv/ComputeCache via getenv("HOME") (C code,
        # no getpwuid fallback -- unlike Python's expanduser). Without it, the
        # first cold-cache run JIT-compiles kernels with no valid cache and can
        # crash with SIGILL / wedge the GPU (observed on the RTX A4000 box,
        # 2026-08-02). run_in_venv builds a minimal env, so HOME must be listed.
        retained_env_vars=[
            "TMP",
            "TEMP",
            "TMPDIR",
            "HOME",
            "TABPFN_TOKEN",
            "TABPFN_MODEL_CACHE_DIR",
            "CAML_COMPUTE",
        ],
    )
