# Troubleshooting

A running "seen this error → here's the fix" log, cross-referenced from
`STATUS.md` and from GitHub issues. Add an entry whenever a real install or
run failure gets diagnosed — this page is what turns a one-off fix into
durable knowledge instead of tribal memory.

## Orchestrator (dev-sandbox-verified issues, fixed during Phase 0/1)

### `AttributeError: np.NaN was removed in the NumPy 2.0 release`

**Where**: `src/caml/datautils.py`, ported from AMLB's `amlb/datautils.py`.
**Cause**: AMLB was written against numpy 1.x; CAML's orchestrator pins
`numpy>=1.26`, which resolves to numpy 2.x today. `np.NaN` was removed in
NumPy 2.0 (`np.nan` still works, lowercase).
**Fix**: replaced all `np.NaN` with `np.nan` in `datautils.py`.

### `ModuleNotFoundError: No module named 'pip'`

**Where**: `src/caml/utils/modules.py`, ported from AMLB's
`amlb/utils/modules.py`.
**Cause**: that module imported `pip._internal.main` for a runtime
"pip install a module" helper. `uv`-managed venvs don't ship `pip`
preinstalled by default (uv doesn't need it), so the import failed at
package load time — before any framework was even touched.
**Fix**: dropped the dead `pip_install`/`pip_main` code entirely (confirmed
unused elsewhere in the ported codebase) — this is exactly the runtime
install path `caml.frameworks.installer` (uv-based) replaces.

### `ModuleNotFoundError: No module named 'boto3'`

**Where**: `src/caml/datasets/fileutils.py`, ported from AMLB's
`amlb/datasets/fileutils.py`.
**Cause**: `S3Handler` imported `boto3` at module level, for `s3://`
dataset URL support. CAML doesn't depend on `boto3` (no AWS runner — see
CLAUDE.md decision #2) but the *dataset-loading* code path is otherwise
still useful for anyone with S3-hosted custom datasets.
**Fix**: made the `boto3`/`botocore` imports lazy (inside `S3Handler`'s
methods, not at module top level) — `uv pip install boto3` if you actually
need S3 dataset support, otherwise the rest of CAML works without it.

### `AttributeError: module 'logging' has no attribute 'TRACE'`

**Where**: `src/caml/datautils.py` (`Encoder.transform`), surfaced as a
wrapped `ResultError` during results processing.
**Cause**: `caml/logger.py` sets the custom `logging.TRACE` level as a
module-level side effect, but `caml/__init__.py` is intentionally lazy
(see its docstring / the `openml` entry above) — so nothing guaranteed
`caml.logger` had actually been imported before `datautils.py` checked
`logging.TRACE`. A real regression introduced by the lazy-import fix
above, caught immediately by actually running a framework end-to-end
rather than just importing the package.
**Fix**: moved `logging.TRACE = getattr(logging, "TRACE", 5)` into
`src/caml/utils/__init__.py` — the one leaf module guaranteed to be
imported early everywhere (including inside a framework's own venv via
`frameworks/shared/utils.py`), independent of whether `caml.logger`
specifically has run yet.

### `ModuleNotFoundError: No module named 'filelock'`

**Where**: `src/caml/utils/process.py::file_lock`, used by
`benchmark.py::_save_global` when writing the cross-run aggregate
`output/results.csv`.
**Cause**: ported from AMLB but never added to CAML's own `pyproject.toml`
dependencies.
**Fix**: added `filelock>=3.13` to `[project.dependencies]`.

### `AttributeError: 'DataFrame' object has no attribute 'append'`

**Where**: `src/caml/results.py`, two call sites (`Scoreboard.append()` and
the "new format" migration path in the CSV writer).
**Cause**: `DataFrame.append()` was deprecated in pandas 1.4 and removed
in pandas 2.0 — AMLB was written against pandas <2.0. CAML's orchestrator
pins `pandas>=2.2`, which resolves to pandas 3.0.3 today.
**Fix**: replaced both call sites with `pd.concat([...])`.

### `NoResultError: Object of type ArrowStringArray is not JSON serializable`

**Where**: `src/caml/utils/serialization.py::is_serializable_data`/`serialize_data`,
surfaced inside a framework's subprocess (first seen with MLJAR-supervised)
when writing its result back across the venv boundary
(`frameworks/shared/callee.py::call_run`).
**Cause**: pandas 3.0 made Arrow-backed dtypes the default for string
columns. Code that used to get a plain `numpy.ndarray` back from
`.values`/`.to_numpy()` on a string-dtype Series (e.g. class labels,
`preds["label"].values`) can now get a `pandas.arrays.ArrowStringArray`
instead — a type neither AMLB's original `is_serializable_data` (which
only recognized `np.ndarray`/`scipy.sparse.spmatrix`/`pd.DataFrame`/`pd.Series`)
nor raw `json.dumps` know how to handle, so it fell through to the JSON
fallback path and crashed.
**Fix**: `is_serializable_data` now also recognizes
`pandas.api.extensions.ExtensionArray` (the base class Arrow-backed arrays,
nullable-integer arrays, etc. all subclass); `serialize_data` converts any
such value to a plain `numpy.ndarray` via `.to_numpy()` before dispatch.
Fixed centrally in the shared serialization boundary rather than patching
individual frameworks' `exec.py` files — this will bite any framework that
touches a string-labeled column and only shows up with real pandas 3.x
data, not from just importing the package, which is why it wasn't caught
until actually running the full pipeline.

### Working-directory drift during multi-step terminal sessions

Not a code bug, but cost real time during Phase 0/1: earlier `cd`
navigation into `automlbenchmark-reference/` (to inspect AMLB's original
source) left the shell's cwd there for later commands that assumed they
were running from the CAML repo root, producing confusing "wrong venv" /
"wrong Python version" symptoms that looked like real bugs but weren't.
**Lesson for future sessions**: `cd` explicitly (or use a full absolute
path) before any `uv run`/`caml` command rather than relying on an
assumed cwd, especially after a research detour into the reference clone.

## VPS provisioning (Phase 2, 2026-07-21)

### `git clone <private CAML repo>` fails on a fresh VPS

**Where**: the manual "reproduce the workspace layout" step in
`docs/getting-started/vps-bootstrap.md` (original version).
**Cause**: the CAML repo was private (until v1.0.0, 2026-10-24) and a
fresh VPS has no GitHub credentials, so the documented `git clone` step
silently fails — the single biggest hole in the "100% automation" story.
**Fix**: repo delivery no longer relies on git-on-the-box. `scripts/provision_vps.sh`
pushes a `git archive` of the committed `HEAD` (tracked files only) over the
same SSH connection the operator already has, and `scripts/setup_workspace.sh`
extracts it — no credential ever lands on the VPS. A git-based flow is still
supported (set `CAML_SRC`/`CAML_REPO_URL` to a URL) for boxes that *do* have
a deploy key, but it's not the default. See `vps-bootstrap.md`.

### `rsync` into a not-yet-existing remote directory fails

**Where**: staging files onto the VPS during provisioning (operator-side, not
CAML code).
**Cause**: `rsync local /tmp/newdir/file` fails with
`change_dir ... failed: No such file or directory` — rsync won't create an
intermediate remote directory when the destination is a file path.
**Fix**: `mkdir -p` the remote directory first, or rsync a directory with a
trailing slash. Noted so the next person automating a transfer doesn't lose a
round-trip to it.

### Non-bugs worth not chasing

- **`nvidia-nccl-cu12` (~289MB) pulled by FLAML/MLJAR on a CPU box.** It's a
  transitive dependency of xgboost's Linux wheel, unused without a GPU. Pure
  disk/bandwidth, no correctness impact. Left as-is; the CPU-only-index
  treatment used for torch frameworks could be extended to xgboost later if
  disk pressure shows up, but it's not worth doing speculatively.
- **`duration: nan` in the per-fold "Metric scores" log line.** The
  aggregated `output/results.csv` has the real per-job durations; job-level
  duration is simply attached after that particular debug log fires.
  Cosmetic.

## Shared installer (Phase 3, TPOT bring-up, 2026-07-29)

### `/bin/sh: 1: cannot open 82: No such file` when installing a framework with a non-`==` pin

**Where**: `src/caml/frameworks/installer.py::install()`, the `uv pip install`
step.
**Cause**: `manifest.install.packages` gets joined with spaces straight into
a shell command string (`run_cmd(..., shell=True)`), with no escaping. Every
framework pinned so far used an exact `==` pin, which has no shell meaning —
TPOT was the first to need a comparison operator (`setuptools<82`, see
`frameworks/TPOT/framework.toml`), and the shell parsed `<82` as stdin
redirection from a file literally named `82`.
**Fix**: `install()` now runs every package spec (and extra-index-url)
through `shlex.quote()` before joining into the command string. General fix,
not TPOT-specific — would have bitten the next framework needing any
shell-meaningful character in a pin (e.g. NaiveAutoML's planned `numpy<2`).

## Cross-cutting hardening (Phase 6, 2026-07-30)

### `openml-python` API calls hang indefinitely on a silent server

**Where**: `src/caml/benchmarks/openml.py`, which calls into
`openml._api_calls`'s `requests.Session.get`/`.post` — neither call site
passes a `timeout=`.
**Cause**: `requests` treats an absent timeout as "wait forever." During
a real OpenML API outage earlier in this project, one attempt sat silent
for ~53 minutes before OpenML's own gateway returned a `504`.
**Non-obvious trap**: `socket.setdefaulttimeout()` does **not** fix this
— confirmed empirically with a hung local-socket test (a `requests.get()`
with no explicit `timeout=` kept blocking well past a 15s wall-clock
guard even with `socket.setdefaulttimeout(2)` set beforehand).
`requests`/`urllib3` ignore the socket-level default entirely unless a
`timeout=` kwarg is passed to the actual call.
**Fix**: `src/caml/benchmarks/openml.py::install_default_http_timeout()`
patches `requests.Session.request` directly to apply a 120s default
whenever a caller didn't specify one — the workaround `requests`'
maintainers themselves point to
(https://github.com/psf/requests/issues/3070), since the library has no
built-in process-wide default. Scoped to this module deliberately: it's
orchestrator-only, never imported inside a framework's isolated
subprocess venv, so patching `requests` here can't break a framework
venv that lacks it. Covered by `tests/test_openml_http_timeout.py` (a
real hung TCP listener, not a mock).

## SapientML bring-up (2026-07-31)

### A dependency's own PyPI classifier can claim wheel support it doesn't have

**Where**: `frameworks/SapientML/framework.toml`'s `[python].range`.
**Cause**: `sapientml==0.4.17` claims Python `>=3.10,<3.14`, but its own
`tantivy<0.22,>=0.21` pin locks in `tantivy==0.21.0`, which only publishes
manylinux wheels up to cp312 — no cp313 build exists, and the sdist
fallback fails outright under `uv`'s stricter PEP 621 metadata parsing.
Not a new class of bug for this project (same root cause as LightAutoML's
`statsmodels` pin and FEDOT's `scipy` pin), but the resolution chain is a
level deeper than usual: it's not `sapientml`'s own classifier that's
wrong, it's a *transitive* dependency's actual wheel availability that
the top-level classifier can't see or account for.
**Fix**: capped `[python].range` at `<3.13`. **Method note**: when a
`uv pip install` failure names a specific sub-dependency (here,
`tantivy`), check that package's own PyPI file listing directly
(`pypi.org/pypi/<name>/json`) rather than assuming the top-level
package's classifier is the ceiling.

### Isolate a failure outside the framework before touching `exec.py`

**Where**: general debugging method, first needed for SapientML's
`TypeError: ndtr() takes from 1 to 2 positional arguments but 3 were
given` (a scipy-internal regression triggered by `sapientml-core`'s own
`scipy.stats.kstest(...)` call, not by anything in CAML's `exec.py`).
**Method**: when a traceback's deepest frames are inside a third-party
dependency (not `exec.py` or CAML's own code), reproduce the failing call
in a standalone script run directly via the framework's own
`venv/bin/python` — no `caml run`, no `SapientML(...)`, just the minimal
call that's actually failing. This is both faster to iterate on (seconds,
not a full multi-job smoke test) and conclusively separates "third-party
bug, needs a version pin" from "our integration is calling the API
wrong." Used to confirm the `ndtr` error and find a working `scipy`
version (`1.14.1`) in a handful of round-trips instead of repeatedly
re-running the full benchmark. See `docs/frameworks/sapientml.md` Part 3
for the full worked example.

## E2E verification harness (2026-07-31)

### A long remote job dies when its driving SSH session ends

**Where**: launching `scripts/verify_e2e.sh` on the VPS.
**Cause**: a bare `ssh root@host "sudo -iu caml bash -lc '... verify_e2e.sh'"`
ties the remote process's lifetime to the SSH connection. A multi-hour
run outlasts the local session that started it; when that session ends
(or the harness tears it down), the dropped connection SIGHUPs the
remote process mid-run. Bit us once — killed the audit after 6 of 11
frameworks (results were preserved on disk, so a resume recovered them).
**Fix**: launch detached — `setsid nohup bash scripts/verify_e2e.sh >
/tmp/log 2>&1 < /dev/null & disown` — so the run has no controlling
terminal and survives the connection closing. Verify survival from a
*fresh, independent* SSH connection (`ps aux | grep verify_e2e`), not the
one that launched it. `verify_e2e.sh` is also now resumable (pass a prior
results dir as `$1`) so an interrupted run doesn't restart from zero.

### Bash associative-array key with `\t` silently mismatches quoted vs. unquoted

**Where**: `scripts/verify_e2e.sh`'s resume skip-set (first version).
**Cause**: `DONE["$fw\t$bench"]=1` (assignment, subscript quoted) stores a
key containing a literal backslash-t, but `${DONE[$fw\t$bench]}` (lookup,
subscript **unquoted**) has its `\t` collapsed to `t` by bash's normal
quote removal (a backslash before an ordinary char is dropped). The two
build different keys, so every lookup missed — the resume was about to
re-run ~8h of already-complete work. **Non-obvious** because the exact
same-looking `[$fw\t$bench]` behaves differently on the two sides purely
from quoting context.
**Fix**: use a delimiter that isn't a backslash escape — `::` here —
which can't appear in a framework/benchmark name and removes the quoting
sensitivity entirely. **Method note**: test shell logic like this by
running it from a real script *file*, not an inline `bash -c "..."` /
`ssh host "..."` command — the outer layer's own quote handling
(especially `$'\t'`) hid the bug during the first ad-hoc check.

## Feature-usage on-VPS verification (2026-09-10)

### `StaleProcessError: ... timed out after nan seconds` on a command that actually succeeded

**Where**: `caml.utils.process.run_subprocess()`, surfaced via `caml install
<fw>` (`uv venv`, `uv python install`) and once mid-`caml run` for
LightAutoML. Hit 3 times on a small (2 vCPU/3.8GB) VPS in one session.
**Symptom**: the traceback shows `timed out after nan seconds` — the `nan`
is not a real value, `run_subprocess()` hardcodes it in the
`StaleProcessError` it raises (`float("nan")`) rather than recording the
actual `activity_timeout` that elapsed, so the message itself carries no
diagnostic info.
**Cause (root-caused, not just worked around)**: `live_output_unix()`'s
read loop (`process.py`) iterates `select.select(pipes, [], [], timeout)`
until both pipes return empty, then `run_subprocess()` checks
`process.poll()`. For a very fast, low-output command (interpreter already
cached, one line of output, exits in milliseconds), there's a benign race
between the child's pipes closing (read loop concludes) and the kernel
fully reporting the exit status via `waitpid` (`process.poll()` still
returns `None` a few microseconds too early) — `run_subprocess()` then
kills the (already-finished) process and raises `StaleProcessError`. For
the one mid-job case (LightAutoML), the same activity-timeout watchdog can
also fire for a real reason: a genuinely long-running subprocess that goes
quiet on stdout/stderr for longer than `activity_timeout` under CPU
contention (e.g. a stray process from an earlier killed job still
competing for the box's 2 cores).
**Verified NOT a real hang**: manually re-running the exact failed command
(`uv venv frameworks/TPOT/venv --python 3.13`) completed in 43ms.
**Fix (2026-09-15)**: `run_subprocess()` no longer trusts a single
immediate `process.poll()` to mean "stale" — if it reads `None`, it now
gives the process a short grace period (`process.wait(timeout=2)`,
`_STALE_PROCESS_GRACE_SECS` in `process.py`) to actually get reaped before
concluding it's genuinely hung and killing it. A process that already
exited (the race case above) resolves within that window with no error; a
process that's truly stuck still gets killed and reported after the grace
period, same as before. Covered by `tests/test_process.py` (a fake
`communicate_fn` mirrors `live_output_unix()`'s instant-empty-reads
behavior against a real subprocess — one test proves the race no longer
raises, another proves a genuine hang still does). Re-verified on a fresh
VPS across 4 separate framework installs (TPOT/GAMA/LightAutoML/FLAML,
each doing `uv python install`/`uv venv`) with zero `StaleProcessError`
occurrences — consistent with, though not conclusive proof of, the fix
(the race is timing-dependent and was never guaranteed to reproduce on
every install anyway).

### Running two frameworks concurrently on a small VPS corrupts one of them

**Where**: GAMA's `caml run` while a TPOT diagnostic script was also
fitting, on the 2 vCPU/3.8GB box.
**Symptom**: `_pickle.UnpicklingError: invalid load key, '@'` inside
GAMA's `AsyncEvaluator.clear_queue()` — a multiprocessing `Queue.get()`
reading a garbled/partial byte stream.
**Cause**: CPU hit ~96% utilization with both frameworks running; CAML's
own per-job timeout enforcement (`raise_in_thread`/`CancelledError`)
interrupted the GAMA job mid-run, and the interruption landed while a
worker was mid-write to the IPC queue, corrupting the read on the other
end. Not a GAMA or CAML bug — genuine resource starvation on an
under-provisioned box.
**Fix**: don't run more than one framework install/run (or diagnostic
script) at a time on a box this small. Sequential-only.

## Feature-usage extraction extension + re-verification (2026-09-15)

### TPOT/GAMA's confirmed structural limitations, now fixed

**Where**: `frameworks/shared/feature_usage.py::used_columns_from_pipeline()`.
**Symptom (not a bug — a confirmed gap)**: as of 2026-09-10, TPOT's
`fitted_pipeline_` wraps any real selector inside a `FeatureUnion`, and
GAMA's `model` always imputes as step 0 before any selector — both shapes
made the old "selector must be the literal first step" rule fall back to
"all columns used" even when a real subset existed.
**Fix**: `used_columns_from_pipeline()` now walks all top-level steps,
tolerating identity-safe steps (`SimpleImputer`, literal `"passthrough"`)
before the selector, and recognizing a `FeatureUnion` as a selector point
when exactly one of its branches is a selector and every other branch is
empty (`"drop"`/`None`). Still returns `None` (safe fallback) for anything
it can't confidently attribute to the original columns — a `FeatureUnion`
mixing a selector with another real transformer, or more than one
selector-capable point anywhere in the pipeline.
**Verified live**: re-ran GAMA on a fresh VPS (10 vCPU / ~2GB RAM) — the iris fold-0 job's `features_used` column came back
`sepallength;petallength;petalwidth` (`n_features_used=3` of 4), the first
time this project has observed a framework's feature-usage columns report
a genuine subset rather than "all columns used". TPOT's short test-budget
fits still didn't pick a selector on this run (same as 2026-09-10), so the
`FeatureUnion`-nested path is unit-tested against real fitted
`sklearn.Pipeline`/`FeatureUnion` objects (`tests/test_feature_usage.py`)
but not yet observed live — would need a longer/wider real TPOT run to
trigger.

## GPU bring-up (Phase 8, 2026-08-02; written up 2026-10-21)

### SIGILL (exit 132) on the first GPU run, no Python traceback

**Where**: any torch framework's first CUDA run on a box with a cold NVIDIA
driver cache. Observed on TabPFN on the RTX A4000 box.
**Symptom**: `caml run TabPFN` dies with exit status 132 = SIGILL (illegal
instruction). It's a native crash, so there's no Python traceback, although
GPU detection had worked (`Using device=cuda`). A standalone diagnostic script
running the same TabPFN fit in the same venv **succeeded**.
**Cause**: `frameworks/shared/caller.py::run_in_venv()` launches each framework
subprocess with a minimal, hand-built environment (only the manifest's
`retained_env_vars`), and that environment didn't include `HOME`. The NVIDIA
driver finds its JIT compute cache (`$HOME/.nv/ComputeCache`) via a bare
`getenv("HOME")` with no fallback. With `HOME` unset, the first-ever CUDA
kernel compile had nowhere valid to cache and crashed. The diagnostic script
(run with `HOME` set) succeeded and warmed the cache, and a later `caml run`
then passed all 6 jobs, which is consistent with this theory.
**Fix**: `HOME` added to `retained_env_vars` in `frameworks/TabPFN/__init__.py`,
`frameworks/AutoGluon/__init__.py` and `frameworks/LightAutoML/__init__.py` (the
three torch frameworks). It was committed in `0be1a35`, bundled with the
feature-usage work.
**Status: not verified.** The GPU box was deleted before a cold-cache re-run,
so treat this as a strong hypothesis with a matching fix, not as confirmed.
Re-verify on the next GPU box with a clean `~/.nv` (see
`operations/known-issues.md`).
**Documentation gap, now closed**: until 2026-10-21 this existed only in the
session transcript and a private memory note, not in the repo. That kind of
gap is what the "document everything" rule exists to prevent.

## Paper-track sweep infrastructure (2026-10-21)

Found while designing `caml sweep` (see `operations/sweeps.md`) — none of
these were visible in small smoke tests, all of them would have corrupted
a paper-scale sweep. Code-read and unit-tested locally; live VPS
verification is pending (see `docs/operations/known-issues.md`).

### `caml run` aborts the whole batch on one job's failure — and writes no row for it

**Where**: `src/caml/cli.py::_bootstrap_resources()` hardcoded
`job_scheduler=Namespace(exit_on_job_failure=True)`.
**Symptom**: the documented 2026-07-31 behavior (TPOT stopping after
`dresses-sales`, SapientML after `diabetes130US`, GAMA after `bioresponse`
on 2026-09-15): one framework exception ends the whole `caml run`, the
remaining tasks never run, **and the failed job leaves no row at all in
`results.csv`**.
**Cause (root-caused 2026-10-21)**: with `exit_on_job_failure` true,
`BenchmarkTask.run()` (`benchmark.py`) re-raises the framework's exception
instead of turning it into an `ErrorResult`, and `Job` is built with
`raise_on_failure=True`, so the job runner stops. AMLB's own default is
the opposite (record an error result, keep going) — CAML's CLI deviated by
hardcoding `True` in Phase 0.
**Why it matters beyond convenience**: a failure that leaves no row is
indistinguishable from "never ran". `caml compare` then silently excludes
that task for that framework, which biases any comparison in favour of
frameworks that fail often. A benchmark paper must report failures, not
lose them.
**Fix**: new opt-in `caml run --keep-going` sets
`exit_on_job_failure=False`, so failures become error rows (message in
`info`, `result` empty) and the run continues. **Default behavior is
unchanged** (abort), since "abort vs. continue" was previously left as an
open design question. `caml sweep` always passes `--keep-going`, *and*
runs each job as its own process, so even a hard crash (segfault, OOM
kill) is isolated and gets classified in the sweep ledger.

### `seed: auto` gives every `caml run` invocation a different random seed

**Where**: `src/caml/resources.py::Resources._seed` — `config.yaml`'s
default `seed: auto` draws `random.randint(1, 2**31-1)` once per process.
**Symptom**: not an error. Within one `caml run`, folds get `seed+fold`;
but two separate invocations (e.g. one `--task` at a time, or a sweep that
runs one process per job) get unrelated seeds, so a re-run can't
reproduce a result. The seed *is* recorded in `results.csv`'s `seed`
column, so past results stay traceable.
**Fix**: new `caml run --seed INT` passes a fixed seed to every job (AMLB
semantics for an int seed: the same value for every fold). `caml sweep`
uses `--seed 42` by default and records the seed in its ledger.

### `app_version` reads `dev [NA, NA]` on every VPS

**Where**: `src/caml/resources.py::git_info` / `app_version`.
**Symptom**: `results.csv`'s `app_version` column says `dev [NA, NA]` for
every row produced on a VPS, so results can't be traced to the code
revision that produced them.
**Cause**: the VPS checkout is a `git archive` (no `.git` — deliberately,
so no GitHub credential lands on the box), so `git rev-parse` fails.
**Fix**: `scripts/lib_package.sh` (used by both `provision_vps.sh` and the
new `sync_vps.sh`) stamps a `REVISION` file (`commit=`, `branch=`,
`dirty=`) into every deployed archive, and `git_info` falls back to it
when there's no git repo. A working-tree deploy with uncommitted changes
records the commit as `<sha>+worktree`. `/REVISION` is gitignored.

**Correction (2026-10-24)**: the symptom above was inferred from reading
the code, never observed, and the fix didn't reach `app_version` at all.
`app_version` only appended the git info when `__version__ == "dev"`
(AMLB's convention). CAML's version was `0.1.0-dev`, so every real row
(4,207 of them in the local `output/`) said just `0.1.0-dev`. See
"`app_version` never recorded the code revision" below.

### Code updates never reached an already-provisioned VPS

**Where**: `scripts/setup_workspace.sh` deliberately skips extraction
when `CAML/` already exists ("already present — leaving as-is").
**Symptom**: re-running `provision_vps.sh` after a code change silently
leaves the old code on the box; sessions on 2026-09-10 and 2026-09-15
both fell back to `scp`-ing individual files by hand.
**Fix**: new `scripts/sync_vps.sh <user@host>` packages HEAD (or the
working tree with `INCLUDE_WORKTREE=1`), refuses to run while a
`caml run`/`caml sweep` is active on the box (swapping code mid-sweep
would mix revisions between jobs; `FORCE=1` overrides), extracts over the
existing checkout as the `caml` user (venvs, install markers, `output/`
and `input/` aren't in the archive, so they survive), and runs `uv sync`.
Known limitation: files deleted locally are not deleted on the box.

## Running locally from an external storage drive (2026-10-21)

Ali moved the runs onto the laptop to avoid VPS costs. The system disk had
about 13GB free, so everything goes on an external NTFS USB drive. Full
setup: `operations/local-storage.md`. Three real problems surfaced while
setting it up.

### A redirected `HOME`/`XDG_CACHE_HOME` never reached most frameworks

**Where**: `frameworks/shared/caller.py::run_in_venv`.
**Symptom (found by code-reading before any run)**: exporting
`HOME=/drive/home` and `XDG_CACHE_HOME=/drive/cache` would have redirected
the orchestrator's own caches, but not those of the framework
subprocesses. HF/TabPFN weights, torch hub, matplotlib and openml caches
would still have landed in the real home directory on the full system disk.
**Cause**: `run_cmd(..., _env_=env)` passes `env` straight to `Popen`, so
it *replaces* the environment rather than extending it. `run_in_venv`
only carried over `TMP/TEMP/TMPDIR` plus a per-framework list (HOME only
for AutoGluon, LightAutoML and TabPFN, since the 2026-08-02 GPU fix).
Python's `expanduser("~")` with no `HOME` falls back to the passwd entry,
i.e. the real home.
**Fix**: new `STORAGE_ENV_VARS` (`HOME` and the four `XDG_*_HOME`) always
cross when set, via a new `retained_env()` helper (unit-tested in
`tests/test_caller_ipc.py`). Behavior-neutral on a normal box. Java
ignores `TMPDIR` (`java.io.tmpdir` defaults to `/tmp`), but h2o-py creates
H2O's `ice_root` with Python's `tempfile`, which honors it. That's still
to confirm live (KI-14).

### `uv` reused a Python interpreter from the system disk

**Symptom**: the first `uv sync` in the drive workspace built `.venv` on
`~/.local/share/uv/python/cpython-3.12.12` (an older uv-managed install on
the system disk), even with `UV_PYTHON_INSTALL_DIR` redirected. uv
discovers interpreters on `PATH` too (`~/.local/bin/python3.12`). Nothing
new was written to the system disk, but the drive wasn't self-contained.
`uv python install` would also have dropped `python3.X` shims into
`~/.local/bin`, clashing with Ali's own.
**Fix**: `caml-env.sh` sets `UV_PYTHON_PREFERENCE=only-managed` and
`UV_PYTHON_BIN_DIR=<drive>/python/bin`. The rebuilt `.venv` uses
`<drive>/python/cpython-3.12.12-.../python3.12`.

### OpenML unreachable from the laptop's network (why local was abandoned)

**Symptom**: `caml run FLAML --benchmark test --constraint test` logged
`Starting [get] request for the URL https://www.openml.org/api/v1/xml/task/3913`
and then nothing for more than 10 minutes. openml-python retries, and
CAML's 120s per-request default timeout restarts on each retry.
**Diagnosis**:
- `curl -m 25` to `www.openml.org` and `api.openml.org` timed out, while
  `pypi.org` and `google.com` answered in under a second through the same
  local HTTP proxy (`HTTPS_PROXY` pointing at a client on `127.0.0.1`).
- `curl -v`: through the proxy, the `CONNECT www.openml.org:443` got no
  reply. Direct (`--noproxy '*'`), TCP connected in **9 ms** (a local
  interception, since a real round trip to TU Eindhoven takes far longer)
  and the TLS ClientHello was never answered.
- From outside (Claude's WebFetch), `www.openml.org` also failed ("Socket
  is closed") while `pypi.org` worked, so OpenML itself may have been down
  at the same time.

**Outcome**: Ali abandoned local runs. Downloads were also only about
2 MB/s. Lesson: before any long run on a new box, check that `openml.org`
answers (KI-07).

### `caml doctor` measured free space on `/`, not where CAML writes

**Fix**: it now measures the filesystem holding the repo/workspace and
prints the path. On the drive workspace it reports 665.5GB free; before,
it would have reported the system disk's ~15GB as "LOW".

## Open-source release prep (2026-10-24)

Three real bugs, all found by the new end-to-end test of the "your own data"
path (`tests/test_file_dataset_pipeline.py`). It runs `caml prepare-data` →
`caml run` → `caml leaderboard` as real subprocesses in a throwaway CAML
root, with a scikit-learn stand-in framework, so it needs no AutoML install.

### Local CSV datasets never loaded: `KeyError: 0` in `load_metadata`

**Where**: `src/caml/datasets/file.py::CsvDatasplit.load_metadata`, ported
from AMLB.
**Symptom**: any benchmark task with a `dataset:` (local file) entry fails
on load with `KeyError: 0` from `pandas/core/series.py`.
**Cause**: `to_feature_type(dtypes[i])`. `dtypes` is a Series indexed by
column name, and pandas 3 removed `Series[int]`'s fallback to positional
lookup. The README advertised local CSV support, but that path had never
been run in CAML: every run so far used OpenML tasks.
**Fix**: `dtypes.iloc[i]`. Two pandas-4 deprecations in the same loader
went with it (`astype(..., copy=False)`, `pat.is_categorical_dtype`).

### `caml run --keep-going` crashed on the first failed job

**Where**: `src/caml/results.py::Scoreboard.as_printable_data_frame`
(`format_low_precision_float`), the same code as upstream AMLB.
**Symptom**: with `--keep-going`, the first framework exception becomes
`TypeError: '<' not supported between instances of 'NoneType' and 'int'`
while saving, and the error row the flag exists to write is lost. Under
`caml sweep` (one `--keep-going` subprocess per job), that job would have
ended as `crash` with no row in `results.csv`.
**Cause**: a failed job's row (and any framework that reports no
`predict_duration`) has `None` durations, and the formatter did `val < 1`.
**Fix**: missing durations format as NaN. Proven with a deliberately
failing test framework: both folds are recorded as error rows, with the
exception in `info`. Confirmed that the test fails without the fix. This
closes the "never exercised against a real failing framework" half of
KI-01, short of a real AutoML failure.

### `app_version` never recorded the code revision

**Where**: `src/caml/resources.py::Resources.app_version`.
**Symptom**: every `results.csv` row and sweep ledger record said
`0.1.0-dev`, so no result could be traced to a commit, despite the
`REVISION` work of 2026-10-21 (see the correction above).
**Fix**: `app_version` now always appends the revision when one is known:
`1.0.0 [main, 3eb1cf7]`, plus `+worktree` for uncommitted changes (a git
checkout with a dirty status) or a `dirty=1` `REVISION`.
`tests/test_sweep.py::test_app_version_falls_back_to_revision_file` asserts it.

### README diagrams: transparency rendered as solid black/white blocks

**Where**: `docs/assets/diagrams/` (TikZ → SVG).
**Symptom**: after adding a banner with translucent glows, the SVGs showed
opaque white or black boxes, and blur shadows rendered as black rectangles.
**Cause**: the `pdflatex` → `dvisvgm --pdf` route doesn't convert PDF
transparency groups. Separately, `\fill[indigo]` in the banner applied the
diagram *node style* named `indigo` (from `styles.tex`), not the colour.
**Fix**: `build.sh` now uses `latex` (DVI) + `dvisvgm` with TikZ's native
`pgfsys-dvisvgm.def` driver (SVG opacity), `shadows.blur` was replaced by a
flat `drop shadow`, and the banner uses `fill=<color>`. Every diagram also
gets a white rounded card on its own lowest layer, so it reads on GitHub's
dark theme.

### Publishing v1.0.0: a fresh history, and the email in commit metadata

**Decision**: KI-47, two repos (Ali, 2026-10-24). **Steps**: the old repo
was renamed `CAML-private` (still private); the local `main` was renamed
`private-main` and pushed there; an orphan `main` holding the v1.0.0 tree
was committed as one commit and pushed to a new public
`A1i-Tabatabaei/CAML`; `v1.0.0` was tagged once CI passed.
**Gotcha 1**: commit and tag metadata are public too. The local git
identity used Ali's personal email, while Ali's GitHub profile keeps its
email private. Public commits use the GitHub noreply address
(`<id>+<login>@users.noreply.github.com`), set as this checkout's
repo-local `user.email`. Check `git config user.email` before committing
from a new clone. Timestamps carry the local UTC offset, so the v1.0.0
commit and tag were made with `TZ=UTC`.
**Gotcha 2**: after a rename, GitHub redirects the old name to the new one
until a repo with the old name exists. The archive remote must point at
`CAML-private` explicitly, not at the old URL, so a push meant for the
archive can't land in the public repo.
**First public CI run**: green (156 passed, 1 skipped, 55 s). Its one
annotation: `actions/checkout@v4` and `astral-sh/setup-uv@v6` target Node 20,
which GitHub deprecated for actions. Bumped to `checkout@v7` and
`setup-uv@v7`, both on Node 24. setup-uv moves no floating major tag after
v7 (v8–v10 exist only as exact versions), so a later bump must pin one.

## macOS as the operator machine (2026-10-24, v1.0.1)

Found while writing an agent prompt for a Mac user. CAML's own runs stay on
the Ubuntu server; three scripts run on the user's machine
(`provision_vps.sh`, `sync_vps.sh`, and `lib_package.sh`, which both source).

### `provision_vps.sh` / `sync_vps.sh` fail on a Mac at the first step

**Where**: `scripts/lib_package.sh::caml_package_archive`, plus one
`mktemp` call in each script.
**Symptom** (expected on any Mac, by inspection, and reproduced on Linux
with BSD-strict stand-ins for `mktemp` and `tar`): `mktemp: illegal option
-- -` from `mktemp --suffix=.tar.gz`, and bsdtar rejecting
`--transform 's,^,CAML/,'`. Every Mac run of the README's setup command
stopped there, before anything reached the server.
**Cause**: `--suffix` and `--transform` are GNU extensions. macOS ships BSD
`mktemp` and libarchive's `bsdtar` (and `/bin/bash` 3.2). The scripts were
only ever run from Linux.
**Fix**: `mktemp -d "${TMPDIR:-/tmp}/caml-....XXXXXX"` (works with both),
and the archive is built by extracting `git archive` (or the worktree file
list) into a staged `CAML/` folder, writing `REVISION` there, and running a
plain `tar czf -C <stage> CAML`. `COPYFILE_DISABLE=1` keeps macOS from
adding `._*` AppleDouble files. Tests: `tests/test_lib_package.py`
(archive layout, REVISION, worktree mode, a BSD-strict shim test that fails
on the old helper, and a static check that the three scripts use no
GNU-only options). CI runs it on `macos-15` with the stock `/bin/bash`.
**Workaround for older clones**: provision from the server itself (the
README's manual route); nothing then runs on the Mac but `ssh` and `scp`.

### `prepare-data` on Excel/Numbers exports: semicolons and encodings

**Where**: `src/caml/prepare.py::read_table`.
**Symptom**: a `;`-separated CSV read as one column, so the target "wasn't
found" and the hint suggested the whole header (`Did you mean: f1;f2;label?`).
A Windows-1252 or Mac Roman export crashed with a `UnicodeDecodeError`
traceback. (A UTF-8 BOM and CRLF line endings were already fine.)
**Cause**: `pd.read_csv` with its defaults: comma separator, UTF-8.
**Fix**: `detect_separator()` reads the header line: a comma wins if
present, otherwise the most frequent of `;`, tab, `|`. In a semicolon file
whose text columns all look like `1,5`, the file is re-read with
`decimal=","`; otherwise those numbers would silently become categories.
Both cases add a `WARNING` saying how the file was read. Non-UTF-8 input
raises a `PrepareError` naming the `iconv` conversion. Encodings are not
guessed: a wrong guess would silently corrupt labels. Tests:
`tests/test_prepare.py` (separator detection, decimal commas, BOM+CRLF,
Mac Roman).

## Windows, macOS and Linux as the operator machine (2026-10-24, v1.1.0)

Ali: "update this new repository to support windows, mac, and linux ... the
goal is for agents to handle running CAML not humans so optimize it for ai
agents ... the agent should first determine what os it's running on and then
choose the right scripts and commands ... (BUT ALL OF THEM SHOULD RUN CAML ON
THE UBUNTU VPS)". The design that came out of it: one server-side command,
`scripts/camlctl` (installed to `/usr/local/bin`), so the operator side is
only `ssh caml-vps camlctl <plain words>` and `scp`, identical on every OS.
On top of that, one operator profile per OS
(`skills/caml-benchmark/references/operator-{windows,macos,linux}.md`) holds
the local commands and gotchas. The entries below are the problems that
shaped it. Unless an entry says "verified", it's established by analysis
and by CI, not yet by a user's agent in the field: the field reports
(`references/field-report.md`) exist to close that gap (KI-16, KI-17).

### Remote commands that only work in one local shell

**Symptom**: the documented shape
`ssh HOST "sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML && uv run caml ...'"`
had already broken repeatedly on quoting from Linux (hence the old "write a
script, scp it, run it" rule in `vps.md`). From other shells it gets worse:
- PowerShell expands `$VAR` and backtick escapes inside double quotes.
- Windows PowerShell 5.1 strips `"` inside an argument passed to a native
  program, and drops empty arguments.
- cmd.exe expands `%VAR%` and doesn't treat single quotes as quotes.
- Interactive zsh doesn't treat `#` as a comment.

A command copied from the docs could do something different on each OS.
**Fix**: `camlctl` does the `sudo -u caml`, the `cd`, the login environment
(uv on PATH, `TABPFN_TOKEN` from `~/.profile`) and the detaching itself, so
every documented server command is plain words. The only raw shell commands
left (setup's first two lines) use one pair of double quotes with no `$`,
backtick, `%`, `!` or inner `"`, which every one of those shells passes
through unchanged. `tests/test_agent_docs.py` lints every `ssh <host> ...`
command in the README, the prompts and the skill against that rule, and
checks that every `camlctl` subcommand they mention exists. CI checks that
the documented strings reach a native program byte for byte. **Verified
2026-10-24** (CI run 40081658794) on:
- Windows PowerShell 5.1.26100 and PowerShell 7.6.7 (Windows Server 2025,
  OpenSSH_for_Windows 9.5p2);
- macOS 15.7 (stock bash 3.2.57 and zsh);
- Ubuntu bash.

The same run confirmed the reason for the rule: in PowerShell,
`"echo $HOME"` reached the program as `echo C:\Users\runneradmin`.

### CRLF line endings from a Windows clone reach the server

**Symptom** (verified locally, 2026-10-24, by simulating Windows' default
`core.autocrlf=true` in a scratch repo): a checkout converts every `.sh` to
CRLF, and **`git archive` applies the same conversion**. So
`provision_vps.sh` run from Git Bash on Windows would push CRLF
`bootstrap_vps.sh` and `setup_workspace.sh`, and bash on the server fails
with `$'\r': command not found`.
**Fix**: `.gitattributes` with `* text=auto eol=lf`. With it, the same
experiment gives LF both in the checkout and in the archive. CI's
`operator-windows` job checks both on a real Windows checkout. **Verified
2026-10-24** on a runner with `core.autocrlf=true`: every `scripts/*.sh` and
`scripts/camlctl` kept LF in the checkout and in `git archive`. Scripts an
agent writes on Windows may still be CRLF, so `camlctl script` strips `\r`
before running them (`tests/test_camlctl.py`; the test fails without the
stripping).

### ssh can't read a config file written by Windows PowerShell 5.1

**Symptom** (verified 2026-10-24 on Windows PowerShell 5.1.26100 with
OpenSSH_for_Windows 9.5p2): `"Host caml-vps ..." > $env:USERPROFILE\.ssh\config`
or `Out-File` writes UTF-16LE with a BOM, and `ssh -G` can't read the file.
PowerShell 7.6 writes UTF-8, which ssh reads. Notepad tends to save a new `config` as
`config.txt`.
**Fix**: the docs create it with a here-string piped to
`Add-Content -Encoding ascii`. CI's Windows job parses that file with
`ssh -G` under PowerShell 5.1 and 7 (both pass). It also writes a config the
wrong way and records what ssh makes of it, which is how the symptom above
was verified.

### `UseKeychain` breaks a shared ssh config off macOS

**Symptom** (verified on OpenSSH 9.6p1, Ubuntu): `Bad configuration option:
usekeychain` and ssh refuses the whole file. That happens when a Mac's
`~/.ssh/config` (with the keychain lines the Mac setup recommends) is
reused on Linux or Windows, for example through dotfiles.
**Fix**: the Mac profile says so, and suggests `IgnoreUnknown UseKeychain` as
the first line. `tests/operator/posix.sh` proves the fix on Linux. The
Windows and Linux configs never include the keychain lines.

### Agent shell tools time out, and SSH sessions drop

**Symptom**: setup takes 5–15 minutes, installs 30–60 and sweeps hours,
while agent shell tools stop a command after 2–10 minutes, and a dropped
SSH session kills its foreground command. The old answer was a hand-written
`setsid nohup ... & disown` line per job, plus guessing from log tails
whether it had finished.
**Fix**: `camlctl start JOB ...` runs any camlctl work command in its own
session and records its PID, command, start and end times, and **exit
code**. `camlctl wait JOB SECONDS` blocks on the server and exits 0, 1 or
124 (still running). `camlctl jobs` shows `lost` when a job has neither an
exit code nor a process (a reboot). `camlctl stop` sends SIGTERM to the
whole session, then SIGKILL to anything left, including processes found by
the `CAMLCTL_JOB` environment marker that every job's processes inherit.

### Excel's default CSV on Windows isn't UTF-8

**Symptom**: Excel's "CSV (Comma delimited)" is Windows-1252 (and with
European regional settings, semicolon-separated with decimal commas).
Since 1.0.1, `prepare-data` refuses it with an `iconv` hint. But the agent
then had to compose an `iconv` command through ssh, and from PowerShell the
quoting made that fragile.
**Fix**: `camlctl dataset FILE` takes the upload into `~caml/data`, reports
`encoding: NOT UTF-8` with `status: needs-conversion` and a ready `fix:`
line, and `--from-encoding WINDOWS-1252` (or `MACINTOSH`) converts it,
keeping the original as `.orig`. CI's server e2e feeds it exactly such a
file (Windows-1252, semicolons, decimal commas, CRLF, an accented category)
and runs it through `prepare-data` and a real FLAML sweep.

### Setup failed on its first CI run: an inherited `XDG_CONFIG_HOME` (verified, fixed)

**Symptom** (CI `server-e2e`, run 40081658794, the first time camlctl setup
ran as root over SSH): `bootstrap_vps.sh` step 2 installed uv into
`/home/caml/.local/bin`, then died with `mkdir: cannot create directory
'/home/runner': Permission denied` and `ERROR: unable to create receipt
directory at /home/runner/.config/uv`.
**Cause**: GitHub's runner image sets `XDG_CONFIG_HOME=/home/runner/.config`
system-wide. Root's SSH session carried it, and `sudo -u caml bash -lc ...`
passed it on to the `caml` user. The uv installer writes its receipt to
`$XDG_CONFIG_HOME/uv`. The same applies to `XDG_CACHE_HOME` (uv's cache) and
`XDG_RUNTIME_DIR`. Any server image with XDG variables in
`/etc/environment` would fail the same way, in the installer or later in
uv and the frameworks.
**Fix**: every switch to `caml` now drops the inherited `XDG_*` variables
(`env -u XDG_CONFIG_HOME -u XDG_CACHE_HOME -u XDG_DATA_HOME -u
XDG_STATE_HOME -u XDG_RUNTIME_DIR`): camlctl's `as_caml`,
`bootstrap_vps.sh` (`as_caml_login`), `provision_vps.sh` and `sync_vps.sh`.
caml's own `~/.profile` can still set them deliberately.
`tests/test_camlctl.py::test_caml_user_commands_drop_inherited_xdg_dirs`
covers it. **Verified** by the next CI run (40082083115, commit `79e39ad`).
The whole agent flow passed as root over SSH in about 4 minutes:
- setup took 55 s;
- the Windows-1252 upload was flagged `needs-conversion`, converted, and
  re-read as UTF-8 with the semicolon separator and 400 rows;
- `prepare-data` chose binary;
- the CRLF helper script ran;
- FLAML installed as a job, and the 2-fold sweep (60 s budget) ended with
  both folds `ok` (AUC 0.762 ± 0.026);
- leaderboard, bundle (43 files), `scp` and unpack all worked;
- `camlctl stop` ended a job and its child through real sudo in 3 s, with
  exit 143.

### Testing notes: two ways the camlctl tests first passed for the wrong reason

- The CRLF test captured output in text mode. Python's universal newlines
  turn `\r\n` into `\n`, so a stray `\r` was invisible, and the test passed
  with the stripping removed. It now uses a script whose CRLF version can't
  print the expected line (`fi\r` is a syntax error). A mutation check
  confirmed it fails without the fix.
- The `stop` test passed with the SIGTERM step removed, because the SIGKILL
  fallback cleaned up after 60 s. It now also asserts that `stop` finishes
  in under 30 s, so it tests the graceful path.

## Framework-specific gotchas

See each framework's own doc page (`frameworks/<name>.md`) for
framework-specific install/runtime gotchas discovered on the real VPS —
kept there rather than duplicated here, since they're scoped to one
framework's manifest/exec.py. The 2026-07-31 messy-data `validation`
benchmark findings (which frameworks handle real-world data-quality edge
cases and which choke) are collected in `operations/e2e-verification.md`.

## The three check-ins: keys, the data's values, the task (2026-10-24, v1.2.0)

Ali asked for three interactions between the agent and the user: an `.env`
file or, better, an interactive script for API keys, the TabPFN key
included; a question about the goal (a benchmark study for an article or
report, or the best model for the rest of the project); and an explicit
confirmation of the task (binary, multiclass or regression, X and y,
whether all the features belong in), even after the agent has probed the
data, anonymizing it first if that hasn't been done. They became
`references/checkpoints.md`, `camlctl secrets`, `caml describe-data` and
`caml anonymize-data`. The entries below are what building them turned up.

### A key stored for `caml` doesn't reach every framework

**Finding**: the first draft of `camlctl secrets` offered an optional
`HF_TOKEN` ("if a Hugging Face download is rate-limited"). But
`frameworks/shared/caller.py::run_in_venv` builds a minimal environment for
each framework subprocess: only `STORAGE_ENV_VARS` (HOME and the XDG dirs)
plus the integration's own `retained_env_vars` cross. `TABPFN_TOKEN` reaches
TabPFN because `frameworks/TabPFN/__init__.py` lists it. An `HF_TOKEN` in
`~caml/.caml-secrets` would have been in camlctl's environment and never in
the framework's, so the offer would have promised something that does
nothing. **Fix**: `SECRETS_KNOWN` lists only `TABPFN_TOKEN`. Other names
can still be stored (they reach camlctl's commands and `camlctl script`),
and a comment in camlctl says a new known key needs a matching
`retained_env_vars` entry. The agent docs say not to promise that a key
reaches a framework.

### The 1.1.0 key file was written by root inside the `caml` user's home

**Finding** (from review, not an incident): `tabpfn-token` ran as root,
created `~caml/.caml-secrets` with `install`, then wrote the key into it
with a second redirection. Between the two, a process running as `caml`
(any framework's code) could replace the file with a symlink, and root
would then write, and truncate, whatever it pointed to. **Fix**: every
write now happens as `caml` (`as_caml ... bash -c "$SECRETS_WRITER"`), into
a `mktemp` file renamed into place, with the values sent over a pipe from
`printf` (a builtin), so a key never appears on a command line or in
`/proc/*/cmdline`. Root never sources the file: `--check` runs in `caml`'s
login shell, and `--import` parses the uploaded file as text, without
evaluating it.

### Hidden input has to be tested on a real terminal

`read -s` only hides input on a TTY, and `ssh -t` is what provides one.
`tests/test_camlctl.py::test_secrets_interactive_input_is_hidden` runs
`camlctl secrets` on a pseudo-terminal (`pty.openpty`), types a key and
asserts that it never shows up in the output. Removing `-s` makes that test
fail (mutation-checked). It waits 0.3 s after each prompt before typing:
characters that arrive before `read` switches echo off get echoed by the
terminal itself. CI's `server-e2e` also runs the prompt for real through
`ssh -tt` and sudo. There it can't assert the key stays hidden, because the
piped input arrives before echo is off, so it only checks that the key was
stored, with a script that compares it in `caml`'s login shell.

### The key was stored, but `caml`'s commands didn't see it (CI, first 1.2.0 run)

**Symptom** (CI run 40094344652, `server-e2e`): `camlctl secrets --import`
reported `TABPFN_TOKEN: imported (14 characters)` and the file existed, but
the check right after it, and every later one, said `TABPFN_TOKEN: missing`.
The unit tests passed, because they run camlctl as an ordinary user without
sudo or a login shell. The 1.1.0 e2e step accepted `token-(set|missing)`,
so it could never have caught this.
**Cause**: the design relied on `caml`'s login shell (`bash -lc`, through
sudo) reading `~/.profile`, where the loader line lives. A bash login shell
reads only the first of `~/.bash_profile`, `~/.bash_login` and `~/.profile`
that exists, so any account with a `~/.bash_profile` skips the loader.
**Fix**: `as_caml` sources `~/.caml-secrets` itself before running anything
as `caml`, in both branches, and the check runs through `as_caml`. So it
reports exactly what jobs and frameworks inherit. The `~/.profile` line stays
for interactive `sudo -iu caml` sessions. A unit test now writes a
`.bash_profile` with no loader and checks that both `--check` and a
`camlctl script` still see the key. Removing the explicit loading makes it
fail (mutation-checked). The e2e step prints which login files `caml` has,
and checks the typed key's value from inside `caml`'s environment.

### Probing data without reading it

An agent that runs `head data.csv` sends rows of the user's data to its
provider. The operator profiles used to list "First lines: `head -n 5`".
They now show the header line only. On the server, `describe-data`
reports kinds, counts and flags. The only values it prints are the target's
class labels, once a target is named, because the user has to confirm them.
`tests/test_describe.py::test_the_text_report_carries_no_cell_values`
checks that no other column's values reach the report. Two things the
first draft got wrong:
- A cancellation-date column, filled in only for the rows that churned, has
  a single distinct value, so it came out as `constant` and was suggested
  for dropping silently. Its emptiness is a perfect leak. There's now a
  `one-value` kind (one value, or empty), and the leak check also tests
  whether a column's emptiness matches the target classes.
- Column names with spaces ("Full Name") can't cross an ssh command line
  unquoted. `describe-data` numbers the columns, and `describe-data`,
  `anonymize-data` and `prepare-data` accept a column's number wherever
  they take its name.

### Anonymization is pseudonymization

`anonymize-data --hash` turns values into HMAC-SHA256 pseudonyms under a
random key that is never stored: equal values stay equal (so a grouped
split still works), and they can't be reversed or matched across runs. It
removes direct identifiers. It can't stop combinations of ordinary columns
(postcode, birth date, job) from singling people out, and both the command's
output and the docs say so. The agent is told to present it that way and
not to call the data "anonymous".
