# SapientML

**Verified** — Tier 2, 2026-07-31 (real VPS). See `STATUS.md`. This page
doubles as the living build guide for this framework: Part 1 distills
AMLB's official "extending the benchmark" docs (the standing gate before
this framework could be started — see `CLAUDE.md`), Part 2 is
SapientML-specific research verified live against real source
(2026-07-31), Part 3 is a chronological build log of the actual
install/runtime problems hit and fixed. Kept as a template for the next
framework brought up this way, not just historical record.

| | |
|---|---|
| PyPI package | [`sapientml`](https://pypi.org/project/sapientml/) (depends on `sapientml-core`, the actual generation engine) |
| GitHub | [sapientml/sapientml](https://github.com/sapientml/sapientml) (org also has `sapientml/core`, `sapientml/automlbenchmark` — see Part 2) |
| License | Apache-2.0 |
| Pinned version | `sapientml==0.4.17` (+ steering pins `nest_asyncio==1.6.0`, `scipy==1.14.1`, see Part 3) |
| Python | `3.12` (range capped `>=3.10,<3.13` — `tantivy`'s pin has no cp313 wheel, see Part 3) |
| System deps | none (confirmed empirically — `lancedb`/`tantivy`/`mecab-python3` all resolved prebuilt wheels, zero apt packages) |
| Last verified | 2026-07-31, real VPS — kc2 AUC 0.668/0.861, iris acc 0.933/1.000, cholesterol RMSE 46.57/54.42 |

## Why it's in the roster

Synthesizes pipelines from a local corpus of human-written pipelines
across many datasets (1,094 pipelines / 170 datasets, per its own docs) —
deterministic/offline, not an LLM-agent tool despite adjacent naming to
"agentic AutoML." It generates actual Python source code for a pipeline
(preprocessing + model), executes several candidates, and keeps the
best-scoring one.

---

## Part 1 — AMLB "extending the benchmark" docs, distilled

Read 2026-07-31 (the standing gate documented in `CLAUDE.md`/`STATUS.md`
before this framework or any framework beyond the original 11-roster could
start). Source: `openml.github.io/automlbenchmark/docs/extending/{, benchmark, constraint, framework}/`.
This distillation maps each AMLB concept to its CAML equivalent — most of
AMLB's own "extending" material describes machinery CAML already replaced
wholesale (Phase 0 decision); the genuinely load-bearing parts are the
`exec.py` contract, which CAML kept ~verbatim.

### Already superseded in CAML (informational only, nothing to act on)

- **`resources/frameworks.yaml` + hand-rolled `setup.sh` per framework** →
  replaced by `framework.toml` + one shared `src/caml/frameworks/installer.py`
  (see `architecture/framework-plugin-contract.md`). AMLB's own maintainers
  flagged this duplication as a maintenance burden (issues #64, #642) —
  exactly the problem CAML's manifest system was built to solve.
- **Docker / Singularity / AWS runners, `docker_commands()`, `-m docker`/
  `-m aws` test modes** → don't exist in CAML at all (locked decision #2,
  bare-metal venv only, no cluster target).
- **`version: "stable"` = `pip install -U` at install time** → CAML uses
  exact-pin-and-deliberately-bump instead (locked decision #4) — this is
  the version-pinning-policy rationale, not new information.
- **`-Xtest_mode` CLI flag, `-s only` setup-only mode** → CAML's equivalent
  test loop is `caml install <name>` then `caml run <name> --benchmark test
  --constraint test` (see `contributing/adding-a-framework.md` step 4-5).

### Still load-bearing — this is what actually governs `exec.py`

1. **The `run(dataset, config)` contract is preserved ~verbatim.** AMLB's
   `frameworks/shared/caller.py::run_in_venv()` / `callee.py::call_run()`
   mechanism — subprocess exec with dataset+config piped over stdin as
   JSON, results read back from a file — is the exact mechanism CAML kept
   (see `CLAUDE.md`'s "isolation mechanism worth preserving" research
   finding, and `architecture/overview.md`). A brand-new framework's
   `exec.py` must implement `run(dataset, config)` and return
   `frameworks.shared.callee.result(...)` — same shape AMLB documents:
   `predictions`, `training_duration`, plus optionally `probabilities`,
   `truth`, `models_count`, `predict_duration`.
2. **No hyperparameter tuning by default.** AMLB's own rule for
   default framework definitions: "Training code must use framework
   defaults plus `**kwargs` for custom params" — no params in the default
   definition, only in a `_custom`-style override. CAML's equivalent is
   `config.framework_params` passthrough (see next point) — every
   framework in this roster follows the same pattern of "call the
   framework's own sensible defaults, let `framework_params` override."
3. **`framework_params` passthrough, `_`-prefix convention preserved.**
   AMLB: "Parameter names starting with `_` are filtered out but available
   for custom logic in `exec.py`." CAML's own convention, already used by
   every framework in the roster (`{k: v for k, v in
   config.framework_params.items() if not k.startswith("_")}`), is exactly
   this rule — confirmed this isn't a CAML invention, it's inherited
   directly from AMLB's own contract.
4. **Standard inputs available to `exec.py`, unchanged in CAML**: problem
   type (`config.type`), column metadata (`dataset`), time/CPU/memory
   constraints (`config.max_runtime_seconds`/`.cores`/`.max_mem_size_mb`),
   objective metric (`config.metric` — "may need translation," AMLB's own
   words; see every framework's `metrics_mapping` dict, e.g.
   `frameworks/AutoGluon/exec.py::get_autogluon_metric()`), random seed
   (`config.seed`), output paths (`config.output_dir`/
   `config.output_predictions_file`).
5. **Prefer file paths over in-memory arrays when the framework supports
   file I/O** — AMLB's explicit guidance to avoid subprocess-serialization
   cost for large arrays. Doesn't universally apply in CAML's case for
   SapientML specifically — see Part 2's Design decisions for why this
   framework ended up using in-memory X/y instead, despite this general
   guidance.
6. **Benchmark/constraint YAML formats** (`resources/benchmarks/test.yaml`,
   `resources/constraints.yaml`) — CAML's own copies are already
   functionally identical to what these docs describe (`name`,
   `openml_task_id`, `folds`, `max_runtime_seconds`, `cores`,
   `min_vol_size_mb`, `__defaults__`/`__dummy-task__` blocks). Nothing to
   change for a new framework — this machinery is problem-agnostic and
   already fully built.

### Not directly applicable but worth knowing

- AMLB supports non-Python frameworks (R via `Rscript`, Java, etc.) through
  an `exec.py` that just shells out (`run_cmd`). Irrelevant here —
  SapientML is a pure-Python library — but confirms CAML's Python-only
  `run_in_venv` mechanism was never actually a limitation for this
  framework.
- AMLB's `extends`/custom-definition-in-`{user_dir}` system for
  hyperparameter variants has no CAML equivalent yet (no framework in the
  roster has needed a `_custom` variant) — `config.framework_params` is
  CAML's answer to the same underlying need (let a user override defaults
  per-run without a second manifest), so this wasn't ported as a separate
  mechanism.

---

## Part 2 — SapientML-specific research (verified live, 2026-07-31)

**Correction to prior sessions' assumption**: CLAUDE.md/STATUS.md
previously stated SapientML has "no confirmed working AMLB reference
implementation." That was wrong — verified this session by actually
reading the files. Two real reference implementations exist:

- `openml/automlbenchmark`'s `frameworks/SapientML/{exec.py,setup.sh,__init__.py}`
  (in the local `automlbenchmark-reference/` clone).
- `sapientml/automlbenchmark` — a fork maintained by the SapientML team
  itself (their GitHub org also has `core`, `loaddata`, `preprocess`,
  `docs`, `web`, `webapp` repos). Its `exec.py` is nearly identical to the
  generic-AMLB copy, with one addition (`config.framework_params`
  extraction, though never actually used) and one **real bug**: `is_multiclass
  = dataset.problem_type = "multiclass"` — a single `=` where `==` was
  clearly intended, which unconditionally overwrites `dataset.problem_type`
  and never actually checks anything. Neither reference wires up
  `config.seed`, `config.metric`, or `config.max_runtime_seconds` at all.

Both are real, plausible, ~90-line implementations — just unpolished and
targeting an old API surface (SapientML has shipped 40+ PyPI releases
since mid-2023; these references likely predate several breaking changes).
Treated as a starting point to diff against current live source, same
discipline as TPOT/LightAutoML/FEDOT — not blindly ported.

### Package structure

`sapientml` (thin, PyPI `sapientml`) depends on `sapientml-core` (PyPI
`sapientml-core`, GitHub `sapientml/core`) — the actual pipeline-generation
engine, registered into the outer package via Python entry points
(`sapientml.pipeline_generator`, `sapientml.config`, etc.). Confirmed via
`sapientml-core`'s `pyproject.toml`:
```toml
[project.entry-points."sapientml.pipeline_generator"]
sapientml = "sapientml_core:SapientMLGenerator"
[project.entry-points."sapientml.config"]
sapientml = "sapientml_core:SapientMLConfig"
```
Both packages get installed transitively via `pip install sapientml`
(`sapientml-core>=0.8.0` is in `sapientml`'s own `Requires-Dist`) — no need
to pin `sapientml-core` separately in `framework.toml`.

### Dependency tree (confirmed via PyPI JSON API, both packages)

`sapientml==0.4.17` direct deps: `numpy<3,>=1.19.5`, `numba<0.65,>=0.61`,
`pandas<3,>=2.0.3`, `pydantic<3,>=2.1.1`, `lancedb<0.6,>=0.5.3`,
`tantivy<0.22,>=0.21`, `setuptools>=65.0.0`, `sapientml-core>=0.8.0`.

`sapientml-core==0.8.0` pulls in a genuinely heavy tree: `catboost`,
`lightgbm`, `xgboost`, `optuna`, `shap`, `scikit-learn<2,>=1.6.1`,
`scipy<2,>=1.14.0`, `seaborn`, `nltk`, `langdetect`, `libcst` (Python
AST/CST manipulation — used for code generation), `jinja2` (templating),
`nbconvert`/`nbformat`/`ipykernel` (it can emit Jupyter notebooks —
`add_explanation` config flag), and — non-obviously — `mecab-python3` +
`ipadic` (Japanese morphological analysis; SapientML's maintainer is
Fujitsu, this is almost certainly for robustly tokenizing text-like
columns regardless of language, paired with `langdetect`). This is one of
the heaviest dependency trees in the whole roster, closer to AutoGluon
than to a lightweight framework — budget VPS disk/RAM accordingly.

`lancedb`/`tantivy` role, resolved: **not actually used for corpus
retrieval at inference/predict time** in the code path CAML exercises —
they're `sapientml`'s own direct deps but the pipeline-selection code
(`sapientml_core.seeding.predictor`) uses pre-trained sklearn-style
classifier `.pkl` files, not a vector/full-text search over a live corpus.
Likely used by `sapientml_core.training.project_corpus` (the offline
meta-training pipeline that produced those `.pkl` files in the first
place — irrelevant to end users, only relevant to the SapientML team
re-training their own models) or by `datastore`/`explain` modules not
exercised by a plain `fit()`/`predict()` call. Not confirmed further since
it doesn't block bring-up either way — install just needs the wheels to
resolve.

### No corpus/model download step needed — corrects the old assumption

The old `docs/frameworks/sapientml.md` (and CLAUDE.md's roster table)
assumed SapientML would need a `post_install_script` similar to TabPFN's
old HuggingFace weight pre-warm. **Not needed.** The trained meta-models
that pick which pipeline template to generate ship as real files
committed directly into the `sapientml/core` GitHub repo (confirmed via
GitHub API) and packaged as wheel data — `sapientml_core/models/{PY39,
PY310,PY311}/{pp_models.pkl, mp_model_1.pkl, mp_model_2.pkl,
feature_importance.json}` — a few hundred KB total, no download, no
network access needed at install or run time beyond the normal `pip
install`.

**Non-obvious wrinkle worth knowing**: those trained artifacts only exist
for Python 3.9/3.10/3.11, despite `sapientml-core`'s own classifier
claiming `>=3.10,<3.14`. Confirmed this isn't a hard blocker for 3.12/3.13
by reading `sapientml_core/seeding/predictor.py::predict()` directly:
```python
_versioned = [9, 10, 11]
version_key = python_minor_version if python_minor_version in _versioned else max(_versioned)
base_path = Path(os.path.dirname(__file__)) / f"../models/PY3{version_key}"
```
Python 3.12/3.13 deliberately fall back to the PY311-trained models (the
code comment: "sklearn version is pinned, so pkl is cross-version
compatible"). So Python version choice for this framework is governed by
**wheel availability across the dependency tree** (the usual constraint
for this project — numba/catboost/lightgbm/xgboost/lancedb/tantivy/
mecab-python3 are exactly the kind of C-extension-heavy packages that have
lagged new-Python-version wheel support elsewhere in this roster), not by
the meta-model files. Verify empirically at install, same as every other
framework — don't trust the `>=3.10,<3.14` classifier at face value.

### Live-verified API (from `sapientml/sapientml/main.py` and
`sapientml/core/sapientml_core/params.py`, current `main` branch,
2026-07-31 — NOT from the AMLB reference, which may be stale)

```python
class SapientML:
    def __init__(
        self,
        target_columns: list[str],
        task_type: Optional[Literal["classification", "regression"]] = None,
        adaptation_metric: Optional[str] = None,       # -> config.metric, translated
        split_method: Literal["random", "time", "group"] = "random",
        split_seed: int = 17,                            # train/val split seed, NOT model seed
        split_train_size: float = 0.75,
        split_stratification: Optional[bool] = None,
        model_type: str = "sapientml",
        **kwargs,                                         # -> SapientMLConfig, see below
    ): ...

    def fit(
        self,
        training_data: Union[pd.DataFrame, str],   # DataFrame WITH target column, or a file path
        validation_data=None, test_data=None,        # optional; None -> auto-split from training_data
        output_dir: str = "./outputs",
        codegen_only: bool = False,
    ) -> "SapientML": ...

    def predict(self, test_data: pd.DataFrame) -> pd.DataFrame: ...
```

`**kwargs` on `__init__` flows into `SapientMLConfig` (defined in
`sapientml_core/params.py`), the real "effort/behavior" knobs:

| Field | Default | Relevant to CAML? |
|---|---|---|
| `n_models` | 3 (max 30) | candidate pipelines generated & evaluated |
| `seed_for_model` | 42 | **-> `config.seed`** |
| `hyperparameter_tuning` | `False` | leave default (no-HPO-tuning principle, Part 1 #2) |
| `hyperparameter_tuning_n_trials` | 10 | irrelevant while tuning is off |
| `hyperparameter_tuning_timeout` | 0 | irrelevant while tuning is off |
| `predict_option` | `None` (→ "comply with metric") | see Design decisions below |
| `add_explanation` | `False` | leave off (emits ipynb/EDA artifacts, not needed) |
| `initial_timeout` (inherited from base `Config`) | 600s | **-> `config.max_runtime_seconds`**, see below |

`adaptation_metric` valid strings (from `sapientml/sapientml/macros.py`'s
`Metric` enum, matched case-insensitively **against the enum member
name**, not its value — confirmed by reading `Metric.get()`'s source):
classification: `f1, auc, ROC_AUC, accuracy, Gini, LogLoss, MCC, QWK`;
regression: `r2, RMSLE, RMSE, MAE, MAPE`.

**CAML metric → SapientML `adaptation_metric` translation table** (CAML's
own metric vocabulary confirmed from `resources/config.yaml`: binary
`[auc, logloss, acc, balacc]`, multiclass `[logloss, acc, balacc]`,
regression `[rmse, r2, mae]`):

| CAML `config.metric` | SapientML `adaptation_metric` | Note |
|---|---|---|
| `auc` | `auc` | direct match |
| `logloss` | `LogLoss` | case-insensitive enum-name match |
| `acc` | `accuracy` | CAML abbreviates, SapientML doesn't |
| `balacc` | `accuracy` (fallback) | no balanced-accuracy metric exists in SapientML; closest available, logged as a warning |
| `rmse` | `RMSE` | direct |
| `r2` | `r2` | direct |
| `mae` | `MAE` | direct |
| `mse` | `RMSE` (fallback) | SapientML has no plain MSE; closest available |
| `f1` | `f1` | direct (not in CAML's default lists but a valid metric elsewhere, e.g. `__dummy-task`) |
| `rmsle` | `RMSLE` | direct |

Same defensive pattern as `frameworks/AutoGluon/exec.py::get_autogluon_metric()`
and `frameworks/FLAML/exec.py`'s `metrics_mapping` dict — this isn't a new
convention, it's this roster's established one.

### Design decisions for `exec.py` (reasoned, not copied blindly)

1. **In-memory X/y, not file paths — deliberate deviation from both AMLB
   references.** Both AMLB reference `exec.py` files read
   `dataset.train.path`/`dataset.test.path` as CSV via `pd.read_csv`.
   Checked what CAML's `dataset.train.path` actually resolves to:
   `frameworks/AutoGluon/exec.py` calls `pd.read_parquet(dataset.test.path)`
   directly, meaning CAML's default `Datasplit.path` is **parquet**, not
   CSV. SapientML's own file-path loader
   (`sapientml/sapientml/params.py::_read_file`) only understands `.pkl`
   or falls through to `pd.read_csv` for anything else — silently wrong
   (or a hard decode error) if handed a parquet path. Rather than fight
   CAML's storage format, `exec.py` uses `dataset.train.X`/`.y` (in-memory,
   the dominant CAML convention — FLAML/TabPFN both do this) and builds
   `pd.concat([X, y], axis=1)` itself, since `SapientML.fit()`'s
   `training_data` param accepts a DataFrame directly (confirmed in
   `main.py` — this is in fact the primary usage shown in SapientML's own
   README quickstart, not a fallback path).
2. **Column-name sanitization, kept from the AMLB reference — for a real
   reason, not cargo-culted.** SapientML's pipeline generator emits actual
   Python source code that references column names as identifiers/string
   literals; a column name with spaces or punctuation can produce
   unparseable generated code. Both AMLB references strip
   `[^A-Za-z0-9_.]` from every column name (predictors and target) before
   calling `fit()`. Kept, applied consistently across train/test/target.
3. **One-hot pseudo-probabilities, matching the reference — but with a
   real bug fixed.** SapientML's `predict()` returns hard label
   predictions, not probabilities, so both AMLB references fabricate a
   probabilities matrix via `OneHotEncoder(handle_unknown="ignore")
   .fit_transform(predictions)`. **Bug in both references**: they fit the
   encoder on `predictions` alone and then assign `columns=dataset.target.classes`
   positionally — if SapientML never predicts one of the classes (very
   plausible on kc2/iris's small test folds), the encoder discovers fewer
   categories than `len(classes)` and the column assignment either raises
   or silently mislabels. Fixed by passing `categories=[dataset.target.values]`
   explicitly to `OneHotEncoder`, guaranteeing exactly `len(classes)`
   columns in the correct, stable order regardless of what SapientML
   actually predicted. `dataset.target.values` is already sorted +
   normalized (lowercased/stripped) per `src/caml/data.py`'s `Feature`
   class, so predictions/truth are normalized the same way before
   comparison — same reasoning the AMLB reference had, just confirmed
   against CAML's actual `Feature.normalize()` rather than assumed.
   **Known quality limitation, not fixed**: these are not real
   probabilities (no calibration, just a one-hot of the hard prediction),
   which will look artificially overconfident on any probability-scored
   metric (auc/logloss) — confirmed on the real VPS, iris fold 0 scored
   93% accuracy but a logloss of 2.40, exactly the signature of
   one-hot-as-probability scoring.

   **The `predict_option="probability"` question, resolved (2026-07-31,
   see Part 3): don't use it.** Left at SapientML's own default (`None`,
   "comply with metric requirements"), a probability-needing
   `adaptation_metric` (auc/logloss/ROC_AUC/Gini/MAP_K) makes SapientML
   select a pipeline whose `predict()` output is *not* a single column of
   hard labels at all — observed both a column of raw probability floats
   (kc2, `auc`) and a `KeyError` because the target column wasn't even
   present in the output shape (iris, `logloss`). This isn't
   `predict_option="probability"` cleanly returning a `predict_proba`
   matrix instead of hard labels — it's the *output contract itself*
   becoming unpredictable depending on `adaptation_metric`, in a way this
   integration isn't built to detect and branch on. `exec.py` forces
   `predict_option="default"` explicitly (via `training_params.setdefault`,
   still overridable through `framework_params`) specifically to keep the
   output shape stable regardless of which metric is requested. Real
   calibrated-probability support would mean detecting and parsing at
   least two different output shapes reliably — a real future improvement,
   but a bigger lift than this first pass, and not worth the risk of an
   unpredictable crash mode across the *entire* roster of probability
   metrics for a benchmark harness whose main job is running unattended.
4. **`max_runtime_seconds` → `initial_timeout`, set via
   `training_params.setdefault(...)` so `framework_params` can still
   override.** SapientML has no single top-level time-budget parameter;
   the closest real knob is `Config.initial_timeout`, the per-candidate-
   pipeline execution timeout (default 600s, `n_models` defaults to 3
   candidates). Chose to set `initial_timeout = config.max_runtime_seconds`
   (full budget per candidate, not divided by `n_models`) rather than
   split it — a candidate that legitimately needs the full budget won't
   be truncated artificially, and CAML's own outer `job_timeout_seconds`
   hard-stop (`callee.py`'s `InterruptTimeout`, ~2x the nominal budget)
   already bounds worst-case total wall-clock if all `n_models` candidates
   each use their full allowance. Neither AMLB reference wires this up at
   all (a real, confirmed gap in both) — CAML's version is a genuine
   improvement, following the exact precedent set by
   `AutoGluon/exec.py`'s `time_limit`/`FLAML/exec.py`'s `time_budget`.
5. **`config.seed` → `seed_for_model`.** Neither AMLB reference passes any
   seed at all. `split_seed` (train/val split) is left at SapientML's own
   default (17) rather than also tied to `config.seed`, since CAML's own
   train/test split already happened upstream (SapientML's internal
   split only applies to validation data extracted from the training
   fold) — tying it to `config.seed` would be reasonable too but isn't
   load-bearing for reproducibility of the benchmark's actual
   train/test partition, which CAML controls.

---

## Part 3 — Build log

Chronological. Append here whenever a real problem is hit and fixed —
this is the section future sessions should extend, not just read.

### 2026-07-31 — Research phase complete, `exec.py` not yet written

Completed Part 1 (AMLB docs distillation) and Part 2 (live API research,
including the important corrections above: a real AMLB reference exists,
no corpus download step is needed, Python 3.12/3.13 gracefully degrade to
PY311 meta-models). `framework.toml`/`__init__.py`/`exec.py` are being
written next, based directly on Part 2's Design decisions. Not yet
installed anywhere (local or VPS) — per project policy, `caml install`
only ever happens on the VPS.

**Open questions to resolve empirically once install is attempted** (flagged
here in advance so the next build-log entry can confirm/deny quickly):

- Actual Python-version ceiling once every dependency in the tree
  (catboost/lightgbm/xgboost/numba/lancedb/tantivy/mecab-python3/shap) is
  resolved for real — the `>=3.10,<3.14` classifier is a hint, not a
  guarantee, per this project's now-standard finding across H2O/FEDOT/
  LightAutoML/GAMA.
- Whether `mecab-python3`/mecab itself needs a system-level MeCab binary
  (the Python bindings sometimes assume `libmecab` is present via apt on
  some distros) — if so, this framework would be the second in the roster
  needing an `apt` system package (after H2O's JRE).
- Whether `lancedb`/`tantivy` (Rust-backed) have prebuilt manylinux wheels
  for whatever Python version is settled on, or fall back to a source
  build (would need a Rust toolchain — a new class of problem for this
  project if it happens).
- Real behavior of `initial_timeout`/`n_models` under the `test` constraint
  (600s budget, 2 folds x 3 datasets) — does a full smoke test finish in a
  reasonable wall-clock time given `n_models=3` candidates x up to 600s
  each, or does it need `n_models` trimmed down for the test benchmark
  specifically?

This page will be filled in further (pin, final gotchas, verification
date, framework-status row) as the VPS install/smoke-test loop proceeds.

### 2026-07-31 — First VPS install attempts, two real bugs found and fixed

**Open questions above, resolved:**
- Python ceiling: **capped at `<3.13`**, not just a soft preference.
  `uv` resolved 3.13 first try; `sapientml`'s own `tantivy<0.22,>=0.21`
  pin locks in tantivy 0.21.0, which has manylinux wheels for cp38-cp312
  only (confirmed via PyPI's file listing) — no cp313 wheel, and the
  cp313 source-build fallback fails outright (tantivy 0.21.0's sdist
  `pyproject.toml` doesn't parse under uv's stricter PEP 621 checks:
  missing `project.version`/`project.dynamic`). sapientml's own tantivy
  pin forbids the newer tantivy releases that do ship cp313 wheels, so
  this isn't fixable with a version bump — same class of fix as
  LightAutoML's `statsmodels` pin and FEDOT's `scipy` pin. Fixed by
  capping `[python].range` at `<3.13` in `framework.toml` — Python 3.12
  resolved cleanly with zero further Python-version issues anywhere else
  in the (large) dependency tree.
- `mecab-python3`: **no apt package needed after all** — installed and
  imported cleanly on Python 3.12 with zero system dependencies. The
  speculative "watch for libmecab" flag didn't pan out.
- `lancedb`/`tantivy`: both resolved prebuilt manylinux wheels once the
  Python-version fix above was in place — no Rust toolchain ever needed.
- `n_models`/`initial_timeout` wall-clock behavior: not yet observed —
  install issues below blocked every smoke-test attempt from reaching
  actual pipeline generation until the third attempt. See next entry.

**Bug 1 — undeclared upstream dependency, `nest_asyncio`.** First smoke
test attempt got past install cleanly but `exec.py` crashed immediately
on `from sapientml import SapientML`:
```
ModuleNotFoundError: No module named 'nest_asyncio'
```
`sapientml/executor.py` does a bare `import nest_asyncio` at module load
time, but neither `sapientml==0.4.17` nor `sapientml-core==0.8.0` lists
it in `Requires-Dist` (checked both via PyPI's JSON API — confirmed
absent from both). A genuine upstream packaging gap, not anything CAML
did wrong. Fixed by adding `nest_asyncio==1.6.0` (current PyPI latest)
directly to `framework.toml`'s `packages` list.

**Bug 2 — scipy-internal regression, triggered by `sapientml-core`'s own
loose `scipy<2.0.0,>=1.14.0` pin.** Second attempt got past import and
into real pipeline generation, then crashed inside
`sapientml_core/meta_features.py`'s `_get_num_dist_pvalues()`:
```
TypeError: ndtr() takes from 1 to 2 positional arguments but 3 were given
```
Root cause isolated with a standalone repro (no SapientML involved at
all — just `scipy.stats.kstest(c0, "norm", [c0.mean(), c0.std()])`, a
completely standard, valid `kstest` call): reproduced the exact
`TypeError` against the default-resolved `scipy==1.18.0`. Confirmed this
is a scipy-internal regression, not an `exec.py` or `sapientml_core` bug
— `kstest`'s own `axis_nan_policy_wrapper`/`_masked_apply` dispatch
machinery has changed how it invokes the resolved CDF callable somewhere
between scipy 1.14 and 1.18, now calling `scipy.special.ndtr()` with 3
positional args where current `ndtr()` only accepts 1-2. Web search for
the exact version boundary was inconclusive (found real, unrelated scipy
1.16 regressions along the way — e.g. a 180x `multivariate_normal.cdf`
slowdown, scipy/scipy#23469 — but nothing pinpointing this exact `ndtr`
signature change). Rather than bisect further, tested `scipy==1.14.1`
(the floor of `sapientml-core`'s own allowed range, most likely what its
authors actually tested against) directly against the same isolated
repro — confirmed working. Fixed by adding `scipy==1.14.1` as an exact
steering pin in `framework.toml` (exact rather than a `<` range,
specifically because the precise regression boundary wasn't identified —
1.14.1 is a concretely verified version, not a guessed cutoff).

**Method note for future sessions**: isolating each failure with a
minimal standalone repro script (run directly via the framework's own
`venv/bin/python`, no `caml run` involved) before touching
`framework.toml` again was much faster than re-running the full 6-job
smoke test after every candidate fix — worth doing this first whenever a
failure looks like it's coming from inside a dependency rather than from
`exec.py` itself.

Both fixes applied, reinstalled clean, smoke test re-running — result
pending, see the next entry (or `STATUS.md` if this page hasn't been
updated again yet).

### 2026-07-31 — Two `exec.py`-level bugs found, then a clean 6/6 pass

With both install-level fixes (Bug 1/2 above) in place, the smoke test got
past install and into real pipeline generation for the first time — and
immediately surfaced two more bugs, both in `exec.py`'s own assumptions
about `predictor.predict()`'s output shape, not in SapientML itself.

**Bug 3 — `kc2` (metric `auc`): `predictions` column held raw probability
floats, not hard labels.** `predictor.predict(X_test)[target_col]`
returned values like `0.42`, `0.0644048280533781` instead of `"no"`/
`"yes"`. Downstream, CAML's own results-scoring layer crashed with
`ResultError: y contains previously unseen labels: np.str_('0.0')` when
trying to label-encode a probability value as if it were a class name.

**Bug 4 — `iris` (metric `logloss`): `KeyError` on the target column
itself.** `predictor.predict(X_test)[target_col]` raised `KeyError:
'class'` — the returned DataFrame didn't have a column named after the
target at all.

**Root cause, same for both**: `SapientML(...)`'s `predict_option`
defaults to `None` ("comply with metric requirements" — see
`sapientml_core/params.py`'s `SapientMLConfig` docstring). `auc` and
`logloss` are both in `sapientml`'s own `metric_needing_predict_proba`
list, so SapientML selected/generated a pipeline shaped around
probability output for both jobs — and that pipeline's output DataFrame
shape isn't the same as the hard-label shape every other part of this
`exec.py` (sanitization, the one-hot fix, label normalization) assumes.
This directly resolves the open question flagged in Part 2's Design
decision #3 ("would need live VPS verification") — now confirmed, and
resolved by forcing `predict_option="default"` via
`training_params.setdefault(...)`, not by trying to detect and parse
both possible output shapes. See Part 2's Design decision #3 for the full
updated reasoning.

**Fix verified — full 6/6 pass, real plausible scores, all in line with
every other verified framework on this benchmark**:

| Task | Fold | Metric | Result | Other scores |
|---|---|---|---|---|
| kc2 | 0 | auc | 0.6677 | acc 0.792, logloss 7.48 |
| kc2 | 1 | auc | 0.8615 | acc 0.887, logloss 4.08 |
| iris | 0 | logloss | 2.4029 | acc 0.933 |
| iris | 1 | logloss | 2.22e-16 | acc 1.000 (perfect fold) |
| cholesterol | 0 | rmse | 46.57 | mae 37.29, r2 -0.119 |
| cholesterol | 1 | rmse | 54.42 | mae 43.03, r2 -0.027 |

Total wall-clock for all 6 jobs: **84.955 seconds** — resolves the last
open question from the research phase (whether `n_models=3 x up to 600s
each` would make the smoke test slow). It didn't: each job's actual
`fit()` took 8-13s and `predict()` ~2s on these tiny datasets, nowhere
near the `initial_timeout` ceiling — SapientML finishes its 3 candidate
pipelines quickly when the dataset is small, regardless of how much
budget `initial_timeout` grants. `models_count` correctly reports `3`
(all `n_models` candidates) on every job. `caml doctor` clean afterward,
zero apt packages, zero orphaned processes.

`framework.toml`'s `[notes]` section, this page's header table, and
`STATUS.md`'s framework-status row have all been updated to reflect
`verified`, 2026-07-31 — see those for the condensed summary. Full
`pytest tests/` regression (including `tests/test_e2e_framework_run.py`
with SapientML now installed alongside the other 8) run next, see
`STATUS.md`'s Notes for the result.

### 2026-07-31 — `validation` benchmark findings (messy-data E2E audit)

Passed `test` cleanly, but failed 1 of the 9 messy-data `validation`
tasks (see `docs/operations/e2e-verification.md`), aborting on
**`diabetes130US`** ("missing values not formatted correctly") with
`KeyError: 'str_catg_False'` raised **inside SapientML's own generated
pipeline code** — the synthesized pipeline references a derived
categorical-encoding column that doesn't exist at predict time. This is a
SapientML-internal robustness gap on badly-formatted-missing-value data,
in the code SapientML *generates*, not in CAML's `exec.py` — so not
fixable from the integration side. The earlier `AttributeError:
predict_proba is not available when probability=False` lines in that same
run are the **known-benign** SVC candidate-skip noise (SapientML routes
around a failed candidate internally; already documented under Design
decision #3's `predict_option` discussion), **not** the fatal error.
Documented as an upstream limitation; the other 7 tasks it reached
produced real scores.
