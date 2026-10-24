# CLI reference

All commands: `uv run caml <command> [options]`, run from the CAML repo root
(or anywhere under it — `find_repo_root()` walks upward looking for
`pyproject.toml`+`frameworks/`+`resources/`).

## `caml install <name> [--all] [--latest] [--force]`

Install a framework into its own `uv`-managed venv. `--all` installs every
framework discovered under `frameworks/`; since 2026-10-24 it continues past
a framework that fails to install, then lists the failures (first line of
each error) and exits 1. Before, the first failure stopped the whole run.
`--latest` bypasses the pin for this run only (doesn't touch
`framework.toml`). `--force` reinstalls even if already up to date.

## `caml uninstall <name>`

Remove a framework's venv and `.setup/installed` marker.

## `caml status`

Print live install status for every discovered framework: pin vs.
installed version, resolved Python, verified/stale/not-started.

## `caml doctor`

Sanity-check the environment: `uv` on PATH, each installed-framework's
declared apt system packages present, free disk space on the filesystem
holding the repo/workspace (warns under 50GB; it measured `/` before
2026-10-21, which was wrong for a workspace on another drive), GPU and
compute mode, stray H2O JVM processes (`pgrep -f h2o.jar`). Exits non-zero if a
hard check (uv, apt packages) fails.

## `caml run <name> [--benchmark test] [--constraint test] [--task NAME]... [--fold N]... [--mode run|test]`

Run a framework against a benchmark suite (`resources/benchmarks/<name>.yaml`,
or a path to any benchmark YAML, such as one `caml prepare-data` wrote)
under a runtime constraint (`resources/constraints.yaml`; `quick`, added
2026-10-24, gives 5 minutes per job on all cores). Installs the
framework first if not already installed (`SetupMode.auto`). Repeat
`--task` to run specific tasks only (matched case-insensitively against
each task's name in the benchmark suite); omit to run every task in the
suite. Repeat `--fold` to run specific folds only; omit to run every fold
in the task definitions. Combine both to scope down to a single job
without a throwaway diagnostic script, e.g.:

```bash
caml run FEDOT --benchmark test --constraint test --task kc2 --fold 0
```

Two options added 2026-10-21 for reproducible, failure-tolerant runs
(see `operations/troubleshooting.md`, "Paper-track sweep infrastructure"):

- `--seed INT`: pass this fixed seed to every job. The default is
  `config.yaml`'s `seed: auto`, which draws a fresh random seed **per
  invocation**, so two separate runs aren't reproducible. The seed used is
  always recorded in `results.csv`'s `seed` column.
- `--keep-going`: when a job fails, record it as an error row in
  `results.csv` (empty `result`, exception text in `info`) and continue with
  the remaining jobs. **Without it (the default), the first failure aborts
  the whole run and the failed job leaves no row at all.**
  Until 2026-10-24, `--keep-going` itself crashed on the first failure
  (`TypeError` formatting the failed row's missing duration). Fixed in
  `results.py`, and covered by `tests/test_file_dataset_pipeline.py` with a
  deliberately failing framework.

## `caml sweep <fw>... --benchmark NAME --constraint NAME [options]`

Run the full frameworks × tasks × folds matrix as **one isolated
`caml run --task T --fold F --seed S --keep-going` subprocess per job**,
with an append-only ledger so that re-running the same command resumes.
Each job ends as `ok`, `error`, `timeout`, `killed` (signal, usually the
OOM killer), `crash` or `no_result`. Jobs run fold-major, so a partial
sweep still holds complete paired comparisons. Full guide:
`operations/sweeps.md`.

| Option | Meaning |
|---|---|
| `--benchmark` | Suite name (`resources/benchmarks/<name>.yaml`), a path to a benchmark YAML, or an OpenML suite/task (`openml/s/271`, `openml/t/59`). Required. |
| `--constraint` | Constraint from `resources/constraints.yaml`. Required. |
| `--task NAME` / `--fold N` | Restrict the matrix (repeatable; task match is case-insensitive). |
| `--seed INT` | Seed for every job (default 42). |
| `--shard K/N` | Run only shard K of N: a deterministic round-robin split, so N boxes can share one sweep with no coordination. |
| `--name NAME` | Ledger/log directory `output/sweeps/<NAME>/` (default `<benchmark>-<constraint>`; for a YAML path, its file stem, e.g. `churn-quick`). |
| `--retry-failed` | Also re-run jobs whose latest record is a failure. |
| `--max-jobs N` | Run at most N pending jobs, then stop. |
| `--job-timeout SECS` | Hard wall-clock limit per job (default `2 × budget + 20 min`). The job's whole process group is killed when it's exceeded. |
| `--dry-run` | Print the matrix with each job's status; run nothing. |

```bash
caml sweep FLAML GAMA --benchmark pilot --constraint pilot --dry-run
caml sweep FLAML GAMA --benchmark pilot --constraint pilot           # run, or resume
caml sweep FLAML GAMA --benchmark pilot --constraint pilot --retry-failed
```

Refuses to start if a framework isn't installed, or if another driver
already holds the same sweep's lock. On a VPS, launch it detached
(`setsid nohup ... & disown` from a script file).

## `caml compare <fw1> <fw2> [<fw3>...] [--benchmark NAME] [--constraint NAME] [--alpha FLOAT]`

Statistically compare 2+ frameworks' results already sitting in
`output/results.csv` (run `caml run` first — this command never runs
anything itself). Paired **per task** (mean `result` across each task's
folds — never per fold, since folds are repeated measurements of the same
task, not independent samples; pooling them directly would overstate
significance).

- **2 frameworks**: Wilcoxon signed-rank test (primary, nonparametric) plus
  a paired t-test (secondary cross-check — flagged as less trustworthy
  whenever the compared tasks mix classification and regression metrics,
  since `result` is direction-normalized to "higher is better" but not
  scale-normalized across metric families).
- **3+ frameworks**: a Friedman omnibus test ("do these differ at all?")
  plus a Holm-Bonferroni-corrected pairwise Wilcoxon post-hoc for every
  pair (more conservative than the Nemenyi test used in some ML papers,
  chosen to avoid an extra dependency — a documented trade-off, not an
  oversight).

`--benchmark NAME` restricts the comparison to that suite's task set
(`resources/benchmarks/<name>.yaml`); `--constraint NAME` restricts to that
runtime constraint's rows; both default to no filtering (every row in
`output/results.csv`). `--alpha` (default `0.05`) only changes the
printed significant/not-significant verdict, not the computed p-values.

Degrades gracefully rather than crashing: fewer than 2 shared tasks prints
a clear reason instead of a p-value; identical paired scores report "no
measurable difference"; a framework with no matching rows after filtering
raises a clear error listing what IS available.

**Averages ALL matching rows currently in `output/results.csv`**,
including any earlier `caml run` invocations of the same task/framework/
fold — the file is append-only and not deduplicated across sessions. For
a comparison scoped to one specific run, filter by `--constraint`, or
pre-filter `output/results.csv` yourself before running `caml compare`.

```bash
caml compare FLAML MLJARSupervised --benchmark test --constraint test
caml compare FLAML TPOT GAMA LightAutoML --benchmark validation --constraint test
```

## `caml prepare-data <file> --target COL [options]`

**Added 2026-10-24.** Turns one CSV, TSV or Parquet file into a CAML
benchmark: `--folds K` (default 5) stratified k-fold splits for
classification, plain k-fold for regression, or `--folds 1 --test-size F`
for a single holdout. It writes `input/datasets/<name>/` (gitignored), which
contains `<name>_train_<k>.csv` / `<name>_test_<k>.csv`, the benchmark
definition `<name>.yaml` (absolute paths; pass it to `--benchmark`), and
`dataset.json` (the source SHA-256, counts, seed, split method, CAML
version).

| Option | Default | |
|---|---|---|
| `--target COL` | required | Column to predict (case-sensitive; close matches are suggested) |
| `--type auto\|binary\|multiclass\|regression` | `auto` | Printed with its reason. An integer target with ≤10 values becomes multiclass with a warning. |
| `--folds K` | 5 | 1–20 |
| `--test-size F` | 0.2 | Only with `--folds 1` |
| `--drop COL` | — | Repeatable; IDs and leaky columns |
| `--name NAME` | file stem | Sanitized to `[A-Za-z0-9_-]` |
| `--seed N` | 42 | Same file + seed = identical folds |
| `--out DIR` | `<repo>/input/datasets` | |
| `--force` | off | Overwrite an existing dataset folder (stale fold files are removed) |

Since 1.0.1 it handles spreadsheet exports: a `.csv` whose header line has
no comma is read with the `;`, tab or `|` separator it does have, a
semicolon file whose text columns are all `1,5`-style numbers is re-read
with decimal commas, and both print a `WARNING` saying how the file was
read. A file that isn't UTF-8 is refused with an `iconv` command to convert
it, instead of a `UnicodeDecodeError` traceback.

It always writes `type:` into the YAML. Without it, the file loader
(`FileDataset.type`) infers *regression* for any numeric target, so a 0/1
integer label would silently become a regression task. It drops rows with a
missing target (warning), and refuses: a missing target column, duplicate
column names, classes with fewer rows than folds, and an explicit `--type`
that contradicts the data. It warns about ID-like columns, strong class
imbalance, and True/False labels (KI-05). Code: `src/caml/prepare.py`;
tests: `tests/test_prepare.py`, plus `tests/test_file_dataset_pipeline.py`,
which runs prepare-data → run → leaderboard as real `caml` subprocesses with
a scikit-learn stand-in framework. The agent-facing guide is
`skills/caml-benchmark/references/data-preparation.md`.

## `caml leaderboard [--benchmark NAME|YAML] [--constraint NAME] [--task T]... [--framework F]... [--markdown]`

**Added 2026-10-24.** Ranks frameworks per (task, constraint) by the mean of
`result` across folds (the direction-normalized primary metric), and shows
the metric in its natural direction (`neg_rmse` → rmse, "lower is better"),
the standard deviation, `folds ok/total`, and the mean training time. Failed
folds (an empty `result`) count against `folds ok`, and the latest error
message is listed under the table. A framework whose folds all failed is
unranked. `results.csv` is append-only, so repeated runs of one (framework,
task, constraint, fold) are deduplicated, keeping the latest by `utc`.

Unlike `caml compare`, it works on a single dataset, and it makes no
significance claim. Code: `src/caml/leaderboard.py` (pure pandas); tests:
`tests/test_leaderboard.py`.

## `caml check-versions`

For every discovered framework, GET the PyPI JSON API for its
`[version_check].pypi_package` and compare against `current_pin`. Prints
`UP TO DATE` or `NEW RELEASE AVAILABLE: <version>` per framework. Doesn't
modify anything — bumping a pin is a manual, deliberate edit to
`framework.toml` (see `architecture/version-pinning-policy.md`).

## Global options

`-v/--verbose`: debug-level logging.
