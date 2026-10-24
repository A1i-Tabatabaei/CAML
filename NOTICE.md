# NOTICE — third-party provenance ledger

CAML is licensed under the Apache License 2.0 (`LICENSE`; the short Apache
attribution notice is in `NOTICE`). The portions of the files below that
come from AMLB remain under AMLB's MIT license; each file keeps its
attribution header, and the MIT text is in `THIRD_PARTY_LICENSES/`.

CAML incorporates code adapted from [OpenML AutoML Benchmark](https://github.com/openml/automlbenchmark)
(AMLB), MIT License, Copyright (c) 2018 OpenML. See `THIRD_PARTY_LICENSES/AMLB-LICENSE.txt`
for the verbatim license text.

All entries below reference AMLB commit `dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6`
(2025-04-19, `master`), fetched into the sibling `automlbenchmark-reference/`
clone on 2026-07-17.

Every file listed below also carries an inline attribution header pointing
back to this file.

## Ported ~verbatim (attribution header + import path fix only)

| CAML file | AMLB source |
|---|---|
| `frameworks/shared/caller.py` | `frameworks/shared/caller.py` |
| `frameworks/shared/callee.py` | `frameworks/shared/callee.py` |
| `src/caml/utils/cache.py` | `amlb/utils/cache.py` |
| `src/caml/utils/config.py` | `amlb/utils/config.py` |
| `src/caml/utils/core.py` | `amlb/utils/core.py` |
| `src/caml/utils/modules.py` | `amlb/utils/modules.py` |
| `src/caml/utils/os.py` | `amlb/utils/os.py` |
| `src/caml/utils/process.py` | `amlb/utils/process.py` |
| `src/caml/utils/serialization.py` | `amlb/utils/serialization.py` |
| `src/caml/utils/time.py` | `amlb/utils/time.py` |
| `src/caml/utils/__init__.py` | `amlb/utils/__init__.py` |
| `src/caml/datasets/fileutils.py` | `amlb/datasets/fileutils.py` |
| `src/caml/datasets/openml.py` | `amlb/datasets/openml.py` |
| `src/caml/datasets/__init__.py` | `amlb/datasets/__init__.py` |
| `src/caml/benchmarks/file.py` | `amlb/benchmarks/file.py` |
| `src/caml/benchmarks/openml.py` | `amlb/benchmarks/openml.py` |
| `src/caml/benchmarks/parser.py` | `amlb/benchmarks/parser.py` |
| `src/caml/data.py` | `amlb/data.py` |
| `src/caml/datautils.py` | `amlb/datautils.py` |
| `src/caml/defaults.py` | `amlb/defaults.py` |
| `src/caml/errors.py` | `amlb/errors.py` |
| `src/caml/job.py` | `amlb/job.py` |

## Ported with light modernization

| CAML file | AMLB source | What changed |
|---|---|---|
| `src/caml/logger.py` | `amlb/logger.py` | Renamed the `"amlb"` root logger name to `"caml"` (required for the logger hierarchy to actually catch `caml.*` module loggers). |
| `frameworks/shared/utils.py` | `frameworks/shared/utils.py` | Dropped the unused `load_module`/`load_amlb_module` machinery (confirmed dead in AMLB itself — no framework's `exec.py` calls it). Renamed `AMLB_LOG_TRACE` env var to `CAML_LOG_TRACE`. |
| `src/caml/__init__.py` | `amlb/__init__.py` | Dropped `AWSBenchmark`/`DockerBenchmark`/`SingularityBenchmark` exports (no container/AWS runner in CAML — see CLAUDE.md decision #2). Also made lazy (PEP 562 module `__getattr__`) instead of eagerly importing `Resources`/`Benchmark` at package-init time — AMLB's eager version chains into `openml`/`pandas`, which broke every framework subprocess's `from caml.utils import *` (that import always runs the parent package's `__init__.py` first, and a framework's own minimal venv never has `openml` installed). Confirmed as a real, reproducible crash while bringing up FLAML, 2026-07-17 — see `docs/operations/troubleshooting.md`. |
| `src/caml/results.py` | `amlb/results.py` | Two `DataFrame.append(...)` call sites (`Scoreboard.append`, the CSV-format-migration path) replaced with `pd.concat([...])` — `DataFrame.append` was removed in pandas 2.0; AMLB was written against pandas <2.0, CAML pins `pandas>=2.2` (resolves to 3.0.3 today). 2026-10-24: `format_low_precision_float` returns NaN for a missing (`None`/NaN) duration instead of raising `TypeError` on `None < 1`, which made `--keep-going` lose every failed job's row (the same code is upstream). |
| `src/caml/datautils.py` | `amlb/datautils.py` | `np.NaN` → `np.nan` (removed in NumPy 2.0; CAML pins `numpy>=1.26`, resolves to 2.5.1 today). |
| `src/caml/utils/modules.py` | `amlb/utils/modules.py` | Dropped `pip_install`/`pip_main` (runtime `pip install` via `pip._internal`) — confirmed unused elsewhere in the ported codebase, and `uv`-managed venvs don't ship `pip` preinstalled by default, so the bare import crashed before any framework was even touched. |
| `src/caml/utils/__init__.py` | `amlb/utils/__init__.py` | Added `logging.TRACE = getattr(logging, "TRACE", 5)` at module top — previously only set as a side effect of importing `caml.logger`, which is no longer guaranteed given `caml/__init__.py`'s new laziness (see above). `caml.utils` is the one leaf module guaranteed to be imported early everywhere. |
| `src/caml/datasets/fileutils.py` | `amlb/datasets/fileutils.py` | `S3Handler`'s `boto3`/`botocore` imports made lazy (inside its methods, not module top-level) — CAML has no hard `boto3` dependency (no AWS runner), but S3-hosted custom dataset URLs still work if you `uv pip install boto3` yourself. |
| `src/caml/utils/serialization.py` | `amlb/utils/serialization.py` | `is_serializable_data`/`serialize_data` now also recognize `pandas.api.extensions.ExtensionArray` (converted to `numpy.ndarray` via `.to_numpy()`) — pandas 3.0 defaults string columns to Arrow-backed dtypes, so `.values` on a string-labeled prediction column can return e.g. `ArrowStringArray` instead of a plain numpy array, which neither the original dispatch logic nor raw JSON serialization understood. Found bringing up MLJARSupervised, 2026-07-18. |
| `src/caml/datasets/file.py` | `amlb/datasets/file.py` | 2026-10-24: `CsvDatasplit.load_metadata` uses `dtypes.iloc[i]` instead of `dtypes[i]` (pandas 3 removed `Series[int]`'s positional fallback, so every local CSV dataset failed with `KeyError: 0`); `astype(..., copy=False)` → `astype(...)` and `pat.is_categorical_dtype(dt)` → `isinstance(dt, pd.CategoricalDtype)` (pandas-4 deprecations). |

## Ported, trimmed

| CAML file | AMLB source | What changed |
|---|---|---|
| `src/caml/benchmark.py` | `amlb/benchmark.py` | `setup()` now delegates to `caml.frameworks.installer` directly instead of a dynamically-imported module's own `setup()`/`setup.sh`. Dropped the `run_mode == "script"` recovery-script branch (no `recover_results.py` in v1). `.setup/installed` bookkeeping (`_write_setup_env`, `_mark_setup_start`/`_mark_setup_done`, flat-string version file) replaced by `installer.py`'s structured-JSON marker. `SetupMode.script` removed from the enum. |
| `frameworks/shared/caller.py` (env/PYTHONPATH block only) | `frameworks/shared/caller.py` | `PYTHONPATH` now carries *two* entries, `<root>/src` **and** `<root>`, instead of AMLB's single `<root>` — CAML uses a `src/` layout for `caml.*` (AMLB's `amlb/` package sat directly at the repo root) while `frameworks/` stays at the repo root as `src/`'s sibling, so both need to resolve inside the subprocess (`caml.utils` for `frameworks/shared/utils.py`, `frameworks.shared.callee` for every `exec.py`). Env vars renamed `AMLB_PATH`→`CAML_PATH`, `AMLB_LOG_TRACE`→`CAML_LOG_TRACE`. |
| `src/caml/resources.py` | `amlb/resources.py` | Framework-catalogue loading (`framework_definition`/`_frameworks`, backed by `resources/frameworks.yaml`) replaced by directory-based discovery via `caml.frameworks.registry` (see `src/caml/frameworks/registry.py` docstring). AWS-only `ec2_instance_type`/`ec2_volume_type` task defaulting dropped from `_validate_task`. Backward-compatibility config-key transform rules dropped (CAML's `config.yaml` is new, not migrating from an older AMLB config). `git_info` falls back to a `REVISION` file (2026-10-21), and `app_version` always appends the revision (`1.0.0 [branch, sha(+worktree)]`) instead of only when the version string is exactly `dev` (2026-10-24). |

## Framework integrations ported ~verbatim (API unchanged from AMLB's integration)

| CAML file | AMLB source | Verified against |
|---|---|---|
| `frameworks/FLAML/exec.py` | `frameworks/flaml/exec.py` | FLAML 2.6.0 (2026-04-28) — `AutoML().fit()` API unchanged |
| `frameworks/MLJARSupervised/exec.py` | `frameworks/mljarsupervised/exec.py` | mljar-supervised 1.3.1 (2026-06-11) — `AutoML().fit()` API unchanged |
| `frameworks/FEDOT/exec.py` | `frameworks/FEDOT/exec.py` | FEDOT 0.7.5 (2026-07-30) — `Fedot` class API (incl. the non-obvious `ApiParamsRepository` allowlist behavior for `metric`/`max_pipeline_fit_time`/`preset`) unchanged; see `docs/frameworks/fedot.md` |
| `frameworks/LightAutoML/exec.py` | `frameworks/LightAutoML/exec.py` | LightAutoML 0.4.2 (2026-07-30) — `TabularUtilizedAutoML`'s constructor, `Task`'s valid name strings, and the reader's `class_mapping` attribute unchanged; see `docs/frameworks/lightautoml.md` |

`__init__.py` for the frameworks above follows AMLB's `run()`-delegates-to-`run_in_venv()`
pattern but drops the old `setup()` function (see `benchmark.py` entry above —
setup is no longer delegated to a dynamically-imported module).

## Framework integrations ported with modification (real, documented deviations from AMLB's integration)

| CAML file | AMLB source | What changed |
|---|---|---|
| `frameworks/AutoGluon/exec.py` | `frameworks/AutoGluon/exec.py` | Tabular path only — the time-series branch (`exec_ts.py` and its dispatch) was dropped, since CAML v1 has no time-series benchmark. Installs `autogluon.tabular[all]` rather than AMLB's full `autogluon` meta-package (avoids pulling `autogluon.multimodal`/`autogluon.timeseries`'s large, unused transformers/timm stack). See `docs/frameworks/autogluon.md`. |
| `frameworks/H2OAutoML/exec.py` | `frameworks/H2OAutoML/exec.py` | Dropped the ARFF single/double-quote retry heuristic and `config.ext.monitoring` (AMLB monitoring-subsystem hook no `exec.py` in CAML uses). JVM lifecycle (`h2o.connection().close()` then `.local_server.shutdown()`) kept as-is from AMLB, which already handles it correctly. See `docs/frameworks/h2o.md`. |
| `frameworks/NaiveAutoML/exec.py` | `frameworks/NaiveAutoML/exec.py` | Real API drift fixed: AMLB's reference passes `timeout=`/`execution_timeout=` to the constructor, neither of which exists in current `naiveautoml` — corrected to `timeout_overall`/`timeout_candidate`. Also fixed AMLB's `max_hpo_iterations=1e10` (a Python float; current `naiveautoml` needs an int). Framework ultimately **skipped** after a separate, confirmed-upstream bug unrelated to this port — see `docs/frameworks/naiveautoml.md`. |
| `frameworks/GAMA/exec.py` | `frameworks/GAMA/exec.py` | Dropped the dead `version_leq_20_2_0` branch (confirmed unreachable against the pinned version). See `docs/frameworks/gama.md`. |
| `frameworks/SapientML/exec.py` | `frameworks/SapientML/exec.py` (also cross-checked against the SapientML team's own fork, `sapientml/automlbenchmark`) | Neither AMLB reference wires up `config.seed`, `config.metric`, or `config.max_runtime_seconds` at all, or sets `predict_option` (a real, confirmed-necessary fix — SapientML's own default silently changes `predict()`'s output shape for probability-needing metrics, see `docs/frameworks/sapientml.md`). Switched from AMLB's raw-CSV file-path reading to CAML's own in-memory `dataset.train.data`/X/y convention (CAML's default `Datasplit.path` is parquet, which SapientML's file loader doesn't understand). Fixed a real bug present in both AMLB references: their one-hot pseudo-probability construction assumed every class gets predicted at least once. Full diff and reasoning in `docs/frameworks/sapientml.md` Part 2. |

## Framework integrations rewritten entirely (AMLB's reference targets a superseded upstream API)

| CAML file | AMLB source | Why rewritten, not ported |
|---|---|---|
| `frameworks/TPOT/exec.py` | `frameworks/TPOT/exec.py` | AMLB's reference targets TPOT's pre-2025-rewrite API and does not run as-is against current `tpot` (`config_dict=`→`search_space=`, `scoring=`→`scorers=`/`scorers_weights=`, `evaluated_individuals_`→`evaluated_individuals`). CAML's `exec.py` was written fresh against `tpot` 1.1.0's current API, using AMLB's version only as a structural reference for *what* the integration needs to do, not *how*. Full API diff in `docs/frameworks/tpot.md`. |

## Framework integrations with no AMLB precedent (built from scratch against upstream docs)

| CAML file | Built against | Notes |
|---|---|---|
| `frameworks/TabPFN/exec.py` | Prior Labs' TabPFN OSS docs + source (`github.com/PriorLabs/TabPFN`) | AMLB's `frameworks/` tree has no TabPFN directory at all — no reference to port from or diff against. Runs the local `tabpfn` package on-box (added 2026-07-31; see `docs/frameworks/tabpfn.md`). |
| `frameworks/TabPFNClient/exec.py` | Prior Labs' `tabpfn-client` docs + source (`github.com/PriorLabs/tabpfn-client`) | The hosted-API sibling of `TabPFN`, for boxes with no local compute. Was the original `frameworks/TabPFN` (built 2026-07-30 after the local-package attempt was thought blocked), renamed `TabPFNClient` 2026-07-31 (see `docs/frameworks/tabpfn-client.md`). |

## Rewritten entirely (AMLB provided the idea/requirement, not the code)

- All `frameworks/<Name>/framework.toml` manifests — replace AMLB's per-framework `setup.sh` + `resources/frameworks.yaml` entry (see AMLB issues [#64](https://github.com/openml/automlbenchmark/issues/64), [#642](https://github.com/openml/automlbenchmark/issues/642)).
- `src/caml/frameworks/{manifest.py,installer.py,registry.py}` — the shared installer subsystem.
- `src/caml/definitions.py` — trimmed `TaskConstraint` dataclass (AWS-only `ec2_volume_type` dropped, `max_mem_size_mb` promoted from AMLB's separate `Task` dataclass).
- `src/caml/cli.py` — replaces AMLB's root `runbenchmark.py` script with an installed console-script.
- `src/caml/paths.py` — repo-root discovery for the console-script entrypoint (AMLB's `runbenchmark.py` could infer this from `__file__`, an installed console-script cannot).
- `resources/config.yaml`, `resources/constraints.yaml`, `resources/benchmarks/test.yaml` — trimmed from AMLB's originals (dropped `frameworks:`/`container:`/`docker:`/`singularity:`/`aws:` sections and AWS-only fields; task/metric/constraint content otherwise preserved).
- `scripts/bootstrap_vps.sh` — new, no AMLB equivalent (AMLB's Docker/Singularity Dockerfile templates covered this role there; CAML is bare-metal-only).
- `scripts/setup_workspace.sh`, `scripts/provision_vps.sh` — new, no AMLB equivalent (AMLB had no bare-metal single-box provisioning path). Added in Phase 2 to make fresh-VPS bring-up a one-command, credential-free operation.
- `src/caml/sweep.py`, `caml sweep`, and `caml run --seed/--keep-going` (`src/caml/cli.py`) — new, 2026-10-21. `--keep-going` restores AMLB's own default (record a failed job as an error result and continue), which CAML's CLI had disabled by hardcoding `exit_on_job_failure=True`. The per-job process isolation, ledger, resume, failure classification and sharding have no AMLB equivalent: AMLB's `job_history` re-run support is related in spirit but isn't exposed by CAML's CLI.
- `scripts/sync_local.sh` and `scripts/run_local_detached.sh` (running from a local storage drive, 2026-10-21), and `retained_env()` / `STORAGE_ENV_VARS` in `frameworks/shared/caller.py` (an addition to AMLB's ported `run_in_venv`: HOME/XDG always cross the subprocess boundary) — new, no AMLB equivalent.
- `scripts/sync_vps.sh`, `scripts/lib_package.sh` (the `REVISION` provenance stamp), `scripts/research/*` (the AMLB install audit) — new, no AMLB equivalent. The audit clones and runs the *original* AMLB from GitHub inside a throwaway container, purely as the object of measurement. No AMLB code is copied into CAML by it.
- `resources/benchmarks/pilot.yaml` — new. Its tasks are members of AMLB's official OpenML suites (openml.org/s/271 classification, openml.org/s/269 regression, curated by the AMLB authors; see Gijsbers et al., JMLR 25(101), 2024). Task IDs were read from the OpenML API on 2026-10-21. The selection and descriptions are CAML's own.
- `src/caml/stats.py`, `caml compare` (`src/caml/cli.py`) — new, no AMLB precedent: AMLB's own `amlb_report/` (see "Not ported" below) has descriptive tables/plots only (barplot/heatmap/linplot/pointplot/stripplot), no hypothesis testing at all.
- `src/caml/prepare.py`, `caml prepare-data` (2026-10-24) — new. AMLB documents the file-dataset format (`train`/`test` paths, `target`, `type`) that the generated YAML uses, but has no tool that writes it.
- `src/caml/leaderboard.py`, `caml leaderboard` (2026-10-24) — new. Related in spirit to AMLB's `amlb_report/` tables, but no code was taken from it.
- `skills/caml-benchmark/`, `.claude-plugin/`, `AGENTS.md` (2026-10-24) — new: the agent skill and its plugin packaging.
- `tests/test_file_dataset_pipeline.py` (2026-10-24) — new: runs the real pipeline with a scikit-learn stand-in framework.

## Not ported (out of scope for v1, see CLAUDE.md / STATUS.md)

`amlb/runners/{aws.py,docker.py,singularity.py,container.py}`, `amlb/uploads.py`,
`amlb/frameworks/definitions.py` (replaced, not ported), `amlb_report/`,
`runstable.sh`, `recover_results.py`, `upload_results.py`, `aws_monitor.ipynb`.
All 11 v1-roster framework integrations are now built (see the tables
above) — SapientML was the last, verified 2026-07-31.
