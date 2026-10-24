# Running large sweeps (`caml sweep`)

**Added 2026-10-21** for the paper track (`docs/research/paper-plan.md`).
Status: implemented and unit-tested locally (`tests/test_sweep.py`); the
`--keep-going` error-row path each job relies on is proven end to end with a
failing stand-in framework (2026-10-24, `tests/test_file_dataset_pipeline.py`);
**first live run with real frameworks pending** on the pilot VPS (KI-01 in
`operations/known-issues.md`).

`caml run` runs one framework on one benchmark in one process. That's fine
for smoke tests, but a paper-scale experiment (10 frameworks × dozens of
tasks × 10 folds, over days, on several boxes) needs more. `caml sweep`
drives the whole matrix as **one isolated `caml run` subprocess per job**
and keeps a ledger of what happened to each one.

```bash
uv run caml sweep FLAML AutoGluon H2OAutoML --benchmark pilot --constraint pilot
```

## What it guarantees

| Problem with a plain multi-task `caml run` | What `caml sweep` does |
|---|---|
| One framework crash aborts every remaining task, and the failed job leaves **no row** in `results.csv` (see troubleshooting, 2026-10-21) | Each job is its own `caml run --task T --fold F --keep-going` process. A framework exception becomes an error row; a hard crash, hang or OOM kill only kills that one job, and the ledger records why. |
| Killing a long run loses track of what's done | Append-only ledger; re-running the **same command** resumes, skipping finished jobs. A job interrupted mid-run has no ledger record, so it simply runs again. |
| `seed: auto` = a different random seed per process | A fixed `--seed` (default 42) is passed to every job and recorded. |
| A hung framework blocks the box forever | Hard wall-clock limit per job (default `2 × budget + 20 min`), then SIGTERM → 30s → SIGKILL to the job's **whole process group**. |
| Stray worker processes / H2O JVMs survive a job and eat the next job's RAM | The job's process group is SIGKILLed after *every* job, normal exit included. |
| Two drivers on one box double-run jobs and run out of memory (happened 2026-09-15) | An exclusive lock per sweep directory; a second driver on the same sweep refuses to start. |
| No easy way to split work over boxes | `--shard K/N`: deterministic round-robin split of the full matrix, so N boxes can run one sweep with no coordination. |
| Results not traceable to code | Each ledger record carries the CAML revision (`app_version`, e.g. `1.0.0 [main, 3eb1cf7]`: from git, or on VPS checkouts from the `REVISION` file; it only really carried the revision from 2026-10-24), framework version, seed and host specs. |

## Job order

The matrix is **fold-major**: fold 0 of every task for every framework,
then fold 1, and so on. A sweep stopped early therefore still holds
complete, *paired* comparisons (every framework on the same task/fold
cells), which is what `caml compare` needs, rather than ten folds of the
first framework and nothing for the rest.

## Job statuses

Every finished job gets exactly one status (`caml.sweep.STATUSES`):

| Status | Meaning | Where to look |
|---|---|---|
| `ok` | A `results.csv` row with a real score was written. | — |
| `error` | A row was written but without a score: the framework raised, and `--keep-going` recorded it. | Ledger `detail` = the row's `info` (the exception). |
| `timeout` | Exceeded the sweep's hard wall-clock limit and was killed. A real hang, or a framework ignoring its time budget. | The job log. |
| `killed` | The process died from a signal. **SIGKILL usually means the kernel OOM killer**: confirm with `dmesg -T \| grep -i -E 'killed process\|oom'`. | `dmesg`, the job log. |
| `crash` | Exited non-zero without writing any row. | Ledger `detail` includes the log's last line. |
| `no_result` | Exited 0 but wrote no row. Should never happen; treat it as a CAML bug. | The job log. |

Each failure should then be triaged into **CAML bug** (fix it), **upstream
framework bug** (document it in the framework's page and in
`operations/known-issues.md`), or **budget/resource limit** (document it).
None of them get hidden: the paper reports failures.

## Files

```
output/sweeps/<name>/          # <name> defaults to <benchmark>-<constraint> (a YAML path's stem for <benchmark>)
├── ledger.jsonl               # one JSON record per finished job (latest per job wins)
├── logs/<fw>.<task>.<fold>.log   # full stdout+stderr of that job's `caml run`
└── .lock
```

Scores still go to the usual `output/results.csv`, so `caml compare` works
on sweep output unchanged. A ledger record looks like this (illustrative
values, not a real run):

```json
{"framework": "FLAML", "task": "credit-g", "fold": 0, "benchmark": "pilot",
 "constraint": "pilot", "seed": 42, "status": "ok", "detail": "",
 "returncode": 0, "result": 0.79, "metric": "auc", "framework_version": "2.3.6",
 "app_version": "1.0.0 [main, 312716e+worktree]", "max_runtime_seconds": 600,
 "hard_timeout_seconds": 2400, "wall_seconds": 655.2,
 "started_utc": "...", "ended_utc": "...", "log": "logs/FLAML.credit-g.0.log",
 "host": "pilot-1", "cpus": 8, "mem_gb": 31.3}
```

## Common commands

```bash
# See the matrix and what's done, without running anything
uv run caml sweep FLAML GAMA --benchmark pilot --constraint pilot --dry-run

# Try a couple of jobs first
uv run caml sweep FLAML --benchmark pilot --constraint pilot --max-jobs 2

# Resume after an interruption: just re-run the same command
uv run caml sweep FLAML GAMA --benchmark pilot --constraint pilot

# After fixing a bug, re-run only the jobs that failed
uv run caml sweep FLAML GAMA --benchmark pilot --constraint pilot --retry-failed

# Split one sweep across 3 identical boxes (run one line per box)
uv run caml sweep <frameworks...> --benchmark openml/s/271 --constraint 1h8c --shard 1/3
uv run caml sweep <frameworks...> --benchmark openml/s/271 --constraint 1h8c --shard 2/3
uv run caml sweep <frameworks...> --benchmark openml/s/271 --constraint 1h8c --shard 3/3
```

**On a VPS, always launch a sweep detached**: it runs for hours or days, and
an SSH session dying kills an undetached command (a real failure, see
troubleshooting 2026-07-31). Since 1.1.0, from any operator machine:
`ssh <host> camlctl start sweep caml sweep <frameworks...> --benchmark B
--constraint C`, then `camlctl status` (progress line and the `--dry-run`
status table), `camlctl wait sweep 540` and `camlctl logs sweep`. On the box
itself, the equivalent is a script launched with `setsid nohup bash
run_sweep.sh > sweep.out 2>&1 < /dev/null & disown`. Don't use inline
multi-line SSH strings, which have repeatedly mangled in this project.

## Before launching: preconditions

- Every framework must already be installed (`caml install <fw>`); the
  sweep refuses to start otherwise (`--dry-run` skips this check).
- Don't run other `caml` work on the same box during a timed sweep: CPU
  contention changes what each framework achieves inside its time budget.
  One driver per box for the main sweep. Running two shards on one big box
  is acceptable for the bug-hunting pilot only.
- Use identical hardware for all shards of one sweep (same provider, plan
  and region). Timings and time-budgeted results aren't comparable across
  different CPUs.

## Known limitations (also tracked in `operations/known-issues.md`)

- **Merging shards**: each box writes its own `results.csv` and ledger; a
  merge step (concatenate, de-duplicate) is not built yet. Needed before
  the multi-box main sweep, not for the single-box pilot.
- **`results.csv` has no `benchmark` column**: tasks with the same name in
  different benchmarks (e.g. `kc1` = task 3917 in `validation`, task
  359962 in `pilot`) are only distinguishable by the `id` column or by
  using a distinct constraint (which is why the `pilot` constraint exists).
- **Peak memory per job isn't recorded** yet; OOM shows up only as a
  `killed` status plus `dmesg`.
- `--keep-going` turning a framework exception into an `error` row was
  only code-read until 2026-10-24. Running it against a deliberately failing
  stand-in framework then exposed a crash (`None < 1` while formatting the
  failed row) that would have lost every error row; it's fixed and tested
  now. It **hasn't yet met a real AutoML framework's failure**; the pilot is
  the first real test.
