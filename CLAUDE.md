# CLAUDE.md — CAML project knowledge

Read this file (and `STATUS.md`) at the start of every session before doing
anything else. This file is durable project memory across many sessions —
keep it current as decisions are made or revised.

## Session handoff — read this first

**Newest work (2026-10-24): CAML v1.0.0 is open source and public.** Ali:
"I need you to open-source it and make it public but before that I need
you to update README file and create a visually appealing professional
design of it ... also write a skill for AI agents ... make it ready to
publish for now. we'll proceed based on your plan afterwards." Then, on
the two decisions: "i agree with both the license and having two separate
repos. finish the job and then i'll let you know to go back to the plan."
- **Two repos.** The old private repo was renamed
  **`A1i-Tabatabaei/CAML-private`**: still private, the full development
  history up to `2ec77fd`, an archive that gets no new pushes. The public
  **`A1i-Tabatabaei/CAML`** starts from a fresh single commit (`0050456`),
  tagged `v1.0.0`, with a GitHub release. CI passed on that first push
  (156 passed, 1 skipped). In the local checkout, `origin` is the public repo, `private` is
  the archive, and the branch `private-main` holds the old history.
- **Commit identity**: public commits use Ali's GitHub noreply address
  (repo-local `user.email`), because Ali's GitHub email is private. Keep it
  that way.
- **License**: Apache-2.0 (`LICENSE`, `NOTICE`, `pyproject.toml`),
  confirmed by Ali on 2026-10-24 (KI-40 closed). Version 1.0.0.
- **New commands**: `caml prepare-data` (`src/caml/prepare.py`: one
  CSV/TSV/Parquet file → stratified folds + benchmark YAML with an explicit
  `type`), `caml leaderboard` (`src/caml/leaderboard.py`: per-dataset
  ranking), the `quick` constraint, and `install --all` now keeps going.
- **Three real bugs found by the new pipeline test**
  (`tests/test_file_dataset_pipeline.py`: real `caml` subprocesses, with a
  scikit-learn stand-in framework): local CSVs never loaded under pandas 3;
  `--keep-going` crashed on the first failure; `app_version` never carried
  the git revision. All fixed (troubleshooting, 2026-10-24).
- **Agent skill** `skills/caml-benchmark/` (SKILL.md + 5 references),
  packaged as a Claude Code plugin/marketplace (`.claude-plugin/`; also
  symlinked into `.claude/skills/`). Its citation instruction is
  deliberately transparent: agents add the citation **and tell the user**
  (background in the gitignored `docs/research/.paper-plan-private.local.md`).
- **README redesign**: a TikZ banner and a new workflow diagram. All
  diagrams are now built with latex+dvisvgm (the native SVG driver) on white
  cards that read in GitHub's dark theme (`docs/assets/diagrams/build.sh`).
- **Release files**: `AGENTS.md`, `CITATION.cff`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CHANGELOG.md`, `.github/workflows/ci.yml`.
- **Scrubbed from the public tree**: two deleted-VPS IPs, home paths, the
  proxy client details, and personal jurisdiction notes (moved to the
  gitignored `docs/research/.paper-plan-private.local.md`). **The old git history
  still contains them**, which is why it stays in the private archive and
  the public repo got a fresh history (KI-47 closed).
- **Ali's to-dos on GitHub**: turn on private vulnerability reporting
  (Settings → Code security; `SECURITY.md` points to it) and, if wanted,
  Zenodo. Zenodo archives only releases published *after* the repo is
  switched on there, so the DOI comes with the next release.
- **Next**: the paper-track plan (the VPS pilot) resumes when Ali says so.

**Previous work (2026-10-20/21): the paper track.** Ali wants to publish a
paper about CAML (arXiv first, then possibly a peer-reviewed venue). The
plan, venue research, arXiv rules (endorsement required since
2026-01-21; free) and the experiment designs are in
**`docs/research/paper-plan.md`**. Everything still open (bugs, unverified
fixes, upstream limits, decisions needed) is in the new single register
**`docs/operations/known-issues.md`**. Keep both current.

Two standing rules from Ali this session, both also in memory:
1. **Documentation is the most important thing in this project.** Every
   bug or problem (even unfixed), every feature, and every achievement gets
   written into the repo as it happens, not at the end. Bugs go in
   `troubleshooting.md` and the `known-issues.md` register; features go in
   their reference doc, README and NOTICE; results and decisions go in
   STATUS/CLAUDE and `paper-plan.md`.
2. **Installs and runs happen on a VPS** (back to this rule late on
   2026-10-21). The local attempt failed because OpenML was unreachable
   from Ali's network and downloads ran at about 2 MB/s ("forget about
   local as my network is trash"). Never install onto the laptop's system
   disk. *(The abandoned interim rule, kept for the record:* installs and
   runs **locally, but only on the external drive**
   `/mnt/MIRC/CAML-STORAGE`, through `scripts/sync_local.sh` +
   `caml-env.sh` + `scripts/run_local_detached.sh`. Full runbook:
   `docs/operations/local-storage.md`. Never `caml install`, `uv sync` or
   `pip install` from the dev repo itself. Unit tests via the dev repo's
   existing `.venv` are fine.)*

What landed (local, unit-tested, not yet live): `caml sweep`
(`src/caml/sweep.py`, `docs/operations/sweeps.md`); `caml run --keep-going`
(root cause of the old "abort on first failure, write no row": `cli.py`
hardcoded `exit_on_job_failure=True`) and `--seed`; a `REVISION` provenance
stamp for VPS deploys (`scripts/lib_package.sh`; `resources.git_info`
falls back to it); `scripts/sync_vps.sh`; the `pilot` benchmark and
constraint; and `scripts/research/` (the AMLB install audit, claim A).
Also closed a real documentation gap: the 2026-08-02 GPU SIGILL root cause
and fix (committed in `0be1a35`) had never been written down. Now in
troubleshooting and `gpu.md`, still unverified (KI-10).

**Later the same day: local storage drive instead of a VPS.** The drive is
NTFS over ntfs-3g and probed fine for venvs. One real bug found: `run_in_venv`
replaced the subprocess env, so a redirected HOME/XDG never reached most
frameworks. Fixed with `STORAGE_ENV_VARS`/`retained_env()` in
`frameworks/shared/caller.py`. `caml doctor` now checks the workspace's disk.
The laptop (i7-11370H 4C/8T, 15GB RAM with ~5GB free, RTX 3060 6GB) installs
CPU wheels (`CAML_COMPUTE=cpu`) for the pilot. Its GPU can close KI-10/11
later. **Abandoned hours later** (network: KI-07, troubleshooting
"OpenML unreachable from the laptop's network"); the drive was wiped.
**Next**: Ali provides a VPS. See STATUS.md.

**Previous work (2026-09-15): statistical significance testing (`caml
compare`) added, E2E-verified on real bigger data.** The user asked
whether p-values could help compare frameworks; after an explanation, they
asked for it built in (not a one-off script), E2E-verified against a
bigger/more-realistic dataset than the 3-task toy suite, with docs and
scripts updated. Full design in the approved plan
(a Claude Code plan file outside the repo at the time
— plan files get reused/overwritten across sessions, so treat
this file and `STATUS.md` as the durable record instead).

- **Methodology** (Demšar 2006, the standard reference for comparing
  learners across multiple datasets): paired **per task** (mean `result`
  across folds, never per fold — folds are correlated measurements of one
  task, not independent samples; pooling them directly would
  pseudoreplicate). 2 frameworks → Wilcoxon signed-rank (primary) + paired
  t-test (secondary, flagged less trustworthy when compared tasks mix
  classification/regression metrics, since `result` is direction- but not
  scale-normalized). 3+ frameworks → Friedman omnibus + hand-rolled
  Holm-Bonferroni pairwise post-hoc (chosen over Nemenyi specifically to
  avoid a new `scikit-posthocs` dependency — documented trade-off, more
  conservative).
- **New files**: `src/caml/stats.py` (pure pandas/numpy/scipy, no
  `caml.*`/`Scoreboard` imports — same directly-unit-testable pattern as
  `frameworks/shared/feature_usage.py`), `tests/test_stats.py` (26 tests,
  several with hand-verified exact expected values, e.g. an 8-task
  all-same-sign fixture asserting Wilcoxon's exact `p = 2×(1/2)⁸ ≈
  0.0078`). New `caml compare <fw1> <fw2> [<fw3>...] [--benchmark NAME]
  [--constraint NAME] [--alpha FLOAT]` command in `src/caml/cli.py`.
  `scipy>=1.10` added as an explicit direct dependency (pyproject.toml) —
  was only an undeclared transitive dep of scikit-learn before.
- **Real scipy 1.18.0 edge-case behavior was probed, not assumed**:
  `wilcoxon`/`ttest_rel`/`friedmanchisquare` do NOT raise on zero-variance
  input on this version (warn + return `(0.0,1.0)`/`(nan,nan)`) — required
  a proactive `np.allclose` pre-check, not a bare `try/except`.
  `friedmanchisquare` DOES raise `ValueError` for exactly 2 groups,
  confirming the dispatcher must route 2-vs-3+ frameworks correctly.
- **`Scoreboard.all()` needs `resources.config().output_dir` passed
  explicitly** (same call `benchmark.py`'s own global-board save path
  uses) — called bare it resolves a per-session scores dir, not the
  aggregate `output/results.csv`, and would silently read empty data.
  `results.csv` has no `benchmark` column, so `--benchmark` filtering
  resolves the suite's task-name set via `resources.get().
  benchmark_definition()` + the existing `Benchmark._is_task_enabled()`.
- **Verified locally**: `caml compare FLAML MLJARSupervised --benchmark
  test --constraint test` against this repo's own real 76-row multi-session
  `output/results.csv` history (append-only, not deduplicated — a genuine
  edge case, not synthetic) — real p-values, the mixed-metric-type t-test
  caveat fired correctly, no crash.
- **Verified on the VPS** (the 10 vCPU / ~2GB RAM box): ran FLAML and GAMA against the `validation` benchmark's
  real, bigger OpenML tasks. This box is extremely RAM-tight (a single
  `bioresponse` job alone needs more RAM than the box has free) — the
  full unbounded 9-task sweep across 4 frameworks was abandoned as
  impractical in favor of targeted single-task (`--task <name>`) runs,
  after hitting two real operational lessons in this session: an
  un-detached long SSH command dying in exactly the way
  `docs/operations/e2e-verification.md` already warned about (fixed via
  `setsid nohup ... & disown`, launched from a scp'd script file, never an
  inline multi-line SSH string — those have repeatedly mangled in this
  project), and a stale+relaunched run briefly double-running (caught via
  `free -h` showing 1.7Gi/1.9Gi used, killed before real damage). **Also
  found a real, believable non-CAML bug**: GAMA on `bioresponse` (1776
  columns) under the 60s `test` constraint raised `IndexError: list index
  out of range` in GAMA's own `postprocessing/best_fit.py` — its
  evolutionary search never evaluated a single individual in 60s on a
  dataset this wide, so post-processing selected from an empty list. Not
  fixed (not CAML's bug, would mean changing GAMA's own code) — `caml run`
  already aborts a whole multi-task invocation on the first fatal job
  error (same behavior already documented for TPOT on `dresses-sales`),
  so this just meant recovering the *other* tasks needed one `--task`
  invocation each rather than a multi-task run. **`caml compare FLAML GAMA
  --benchmark validation --constraint test`** against the resulting real
  data: correctly paired 3 shared tasks (eucalyptus, dresses-sales,
  internet-advertisements), correctly EXCLUDED `bioresponse`
  (`excluded_tasks: {bioresponse: [GAMA]}`, printed under "Excluded
  tasks"), real (non-significant, small-n) Wilcoxon/t-test output, correct
  mixed-task-type caveat. Exercises both the real-comparison and
  graceful-exclusion paths against genuinely real, bigger data — judged
  sufficient without the full sweep, which this box's RAM ceiling makes
  impractical. The 3+-framework omnibus path is thoroughly covered by
  unit tests with hand-verified known answers instead (not re-proven live
  on the VPS this session).
- **Docs updated**: `docs/reference/cli.md` (new `caml compare` section),
  `README.md` (new subsection + command-reference row), `NOTICE.md` (new
  "no AMLB precedent" entry), `docs/operations/e2e-verification.md` (new
  closing section on using `caml compare` as a post-audit follow-up).
  `scripts/verify_e2e.sh` now echoes a ready-to-copy `caml compare`
  suggestion per benchmark with ≥2 PASS frameworks (pure `echo`, no new
  failure modes). Local suite: 80/80 (54 prior + 26 new).

**Prior work (2026-09-15): the three standing open items from 2026-09-10
are all closed out.** The user said "proceed with all three of them" and
provided a new VPS (10 vCPU/**~2GB RAM**/29GB disk, details in the gitignored
`docs/operations/.vps-access.local.md`; supersedes the 2 vCPU box). RAM is the tightest box this project has used
yet (below even the previous 3.8GB box); the bootstrap swapfile (4GB) is
doing real work here.

1. **Extended TPOT/GAMA's feature-usage extraction**
   (`frameworks/shared/feature_usage.py::used_columns_from_pipeline()`) to
   handle the two structural limitations confirmed 2026-09-10: a selector
   nested inside a `FeatureUnion` (TPOT's linear template) and a selector
   preceded by an imputation step (GAMA's pipeline always imputes first).
   The walk now tolerates identity-safe steps (`SimpleImputer`, literal
   `"passthrough"`) before the selector and recognizes a `FeatureUnion` as
   a selector point only when it wraps exactly one real (non-`"drop"`)
   branch — still falls back to `None` ("all columns used") for anything
   more ambiguous (mixed-branch unions, multiple selector-capable points).
   6 new unit tests against real fitted `sklearn.Pipeline`/`FeatureUnion`
   objects. **Confirmed live on the new VPS**: GAMA's iris fold-0 job
   genuinely reported a subset — `features_used=sepallength;petallength;
   petalwidth` (3 of 4 columns), `n_features_used=3` — the first time this
   project has observed a real (non-"all columns") result from the
   feature-usage columns. TPOT's short test-budget fits still didn't pick
   a selector on this run, so its `FeatureUnion` path is unit-tested but
   not yet confirmed against a live TPOT fit.
2. **Fixed the `run_subprocess` `StaleProcessError` race**
   (`src/caml/utils/process.py`): the root cause (found 2026-09-10, not
   fixed then) was `run_subprocess()` trusting a single immediate
   `process.poll()` right after `communicate()` returns to mean "the
   process is stuck" — but a process that just exited may not be reaped
   by the OS at that exact instant, so `poll()` could read `None` for an
   already-finished process. Fixed with a short grace period
   (`process.wait(timeout=2)`, `_STALE_PROCESS_GRACE_SECS`) before
   concluding it's genuinely stale and killing it; a real hang still gets
   killed and reported after the grace window, so this doesn't turn a
   real hang into a silent wait. 2 new regression tests
   (`tests/test_process.py`) using a real subprocess + a fake
   `communicate_fn` reproducing the exact race shape (`run_subprocess()`'s
   own default `communicate` blocks for real process exit and can't
   reproduce this race — only a custom `communicate_fn` like
   `live_output_unix()` can). Re-verified across 4 fresh framework
   installs on the new VPS (TPOT/GAMA/LightAutoML/FLAML, each doing
   `uv python install`/`uv venv`) — zero `StaleProcessError` occurrences.
3. **E2E re-verification**: TPOT, GAMA, LightAutoML, FLAML all installed
   and ran cleanly on the new VPS (`caml run <fw> --benchmark test
   --constraint test`), all 6 jobs each with real, plausible scores. Local
   suite: 54/54 (up from 45 — 9 new tests across both fixes).
4. **Committed and pushed** per the user's explicit request, closing out
   the entire 2026-09-06→2026-09-15 feature-usage-reporting arc.

Also updated `scripts/provision_vps.sh` to natively support deploying an
uncommitted working tree (not just committed `HEAD`) — this session (and
2026-09-10's) both needed a manual `git ls-files -co --exclude-standard |
tar czf ...` workaround because `git archive HEAD` only captures the last
commit. See "VPS provisioning" below for the new flag.

**Prior work (2026-09-10): feature-usage reporting verified on a real VPS,
one real bug found and fixed.** Follows directly from the 2026-09-06 entry
below (code-complete, verification blocked on no VPS existing). The user
provided a new box (plain CPU, 2 vCPU/3.8GB RAM/116GB disk,
details in the gitignored `docs/operations/.vps-access.local.md`; not a
GPU replacement, RAM is below this project's own ≥8GB recommendation). Ran
`caml run <fw> --benchmark test --constraint test` for FLAML, TPOT, GAMA,
LightAutoML and inspected `output/results.csv`'s three new columns for
real, plus wrote small standalone diagnostic scripts to inspect each
framework's actual fitted-pipeline object shape directly (not just the
CSV output). Findings:
- **FLAML**: exactly as expected, all-columns on every job.
- **TPOT**: `tpot.fitted_pipeline_` confirmed to really be an
  `sklearn.Pipeline`. These short 60s-budget fits never actually picked a
  selector (steps came back as `Passthrough`/`FeatureUnion` wrappers), so
  "all columns used" was the *correct* report, not a bug. But this
  surfaced a real, now-confirmed limitation: TPOT's linear template nests
  any real selector inside a `FeatureUnion`, which
  `used_columns_from_pipeline()` doesn't look inside — documented in
  `framework.toml`, deliberately not fixed (new scope, flag before
  extending).
- **GAMA**: `gama_automl.model` confirmed to be a real (flatter than
  TPOT's) `sklearn.Pipeline`; no selector chosen in these fits, correct
  fallback. Confirmed limitation: GAMA's pipeline always imputes as step
  0, so a real selector would land at step 1+ and never match the
  "selector must be first" check — documented, not fixed.
- **LightAutoML: found and fixed a real bug.** The original assumption
  (`leaf.used_features` as a plain attribute) was wrong — live
  introspection showed each leaf in
  `outer_pipes[*].ml_algos[*].models[*][*]` is actually a `TabularAutoML`
  wrapper instance exposing a real public method,
  `collect_used_feats() -> List[str]`. Fixed `union_of_branch_features()`
  to support calling a zero-arg method (not just reading an attribute),
  updated the call site to pass `attr="collect_used_feats"`, added 2 new
  tests (local suite now 45/45), re-verified end-to-end on the VPS
  post-fix (clean run, no introspection-failure warning). All three test
  datasets still came back all-columns at this small scale/short budget —
  a wider dataset would be a better test of whether it ever reports a
  genuine subset.

Also found along the way, deliberately not fixed here (pre-existing,
out of scope for this task): a real, reproducible race in
`caml.utils.process.run_subprocess`'s activity-timeout watchdog
(`StaleProcessError ... timed out after nan seconds`), hit 3 times against
very fast one-line commands (`uv venv`, `uv python install`) and once
mid-job under CPU contention — manual retries always succeeded, the
underlying command was never actually hung. Root-caused to a benign race
between pipe-EOF detection and `process.poll()` in `live_output_unix()`/
`run_subprocess()`; worth a real fix if it keeps interrupting VPS work, but
flagged to the user rather than unilaterally patched since it's unrelated
orchestrator infrastructure. Separately: this box is only 2 vCPU — running
two frameworks concurrently once corrupted GAMA's internal multiprocessing
IPC (`_pickle.UnpicklingError`) under contention; don't parallelize
framework runs on this box.

**Prior work (2026-08-02): Phase 8 GPU support — code complete, on-box
verification pending.** The user deleted the CPU VPS and rented a GPU box
(**RTX A4000 / 24 vCPU / 28GB RAM / 320GB SSD**), and asked to install+run
CAML on it and make CAML "optimize for GPU servers by default." Implemented
the full "GPU by default, CPU fallback" design in code (verified by unit tests
+ `caml doctor`/`status` locally; **not yet run on the GPU box** — creds
pending in the new untracked `docs/operations/.gpu-vps-access.local.md`, which
the user fills in). What landed:
- **One knob, both phases:** `CAML_COMPUTE=auto|cpu|gpu` (default `auto`)
  controls install-time wheel choice *and* run-time device. Install-time
  detection = `nvidia-smi` (`installer.py::gpu_present`); run-time =
  `torch.cuda.is_available()` (`frameworks/shared/compute.py`).
- **Install-time:** new manifest field `gpu_extra_index_urls`; the installer
  picks CUDA wheels when a GPU is present, CPU wheels otherwise. Only the three
  torch frameworks declare it → the CPU-bound roster is untouched on any box.
  Recorded in the install marker + shown in `caml status`' new COMPUTE column.
- **Run-time:** `TabPFN` `device` auto → cuda/cpu (**GPU also lifts TabPFN-3's
  CPU >1000-sample guard — the big win**, directly fixes the 6/9 `validation`
  failures); `AutoGluon` gets `num_gpus=1`; `LightAutoML` gets `gpu_ids="0"`
  (`CAML_GPU_IDS` overrides). `TabPFNClient` + CPU-bound frameworks exempt.
- **Docs:** `docs/operations/gpu.md` is the full reference; `bootstrap_vps.sh`
  now reports GPU; `caml doctor` reports GPU + compute mode.
- **Default CUDA wheel index is `cu124`** in the three manifests — the `cuXXX`
  suffix must match the A4000 box's actual driver; **verify with `nvidia-smi`
  on the box and bump if needed** (graceful: a mismatch just falls back to CPU,
  no crash). **On-box TODO:** provision (non-root `administrator`+sudo login,
  see gpu.md), install torch frameworks (confirm CUDA wheels + `torch.cuda`),
  smoke-test, re-run TabPFN `validation` (the >1000-row tasks should now pass
  on GPU), then fill in gpu.md's "Verified on the RTX A4000 box" section +
  STATUS. See the rewritten "Compute target" section below for the full design.

**Newest work (2026-07-31): TabPFN now runs 100% locally.** The user asked
whether TabPFN really needs the hosted API — it doesn't. Added a new local
`TabPFN` framework (OSS `tabpfn==8.1.0`, CPU torch wheel, runs on-box, data
never leaves the machine) and **renamed the previous hosted entry `TabPFN` →
`TabPFNClient`** (the user's choice: local is the primary/default, the API
client stays as the GPU-less fallback). The old "local `tabpfn` is blocked on
a license gate" conclusion (which drove the 2026-07-30 pivot to the client)
was correct at the time but went stale — the blocker was that no Prior Labs
account existed then; once the user had one (created for the client pivot),
the local package worked. The one genuinely-blocking step this pass was a
one-time **TabPFN-3 model-license acceptance** in the user's Prior Labs
account (a user-only action — I can't and shouldn't accept a license; the
token itself was already valid, `verify_token → True`, and the HF weight repo
`Prior-Labs/tabpfn_3` is ungated). Once accepted, `caml run TabPFN --benchmark
test --constraint test` passed 6/6 with real scores (kc2 AUC 0.855/0.910, iris
acc 1.000/1.000, cholesterol RMSE 43.69/54.08), `device="cpu"`, no `exec.py`
bugs. Two frameworks now: `frameworks/TabPFN` (local, `docs/frameworks/tabpfn.md`)
and `frameworks/TabPFNClient` (hosted, `docs/frameworks/tabpfn-client.md`).
**License flag:** TabPFN-3 *weights* are non-commercial — legal read needed
before any result using the local framework leaves internal use. **Follow-up
(done 2026-08-01):** ran the local `TabPFN` through the `validation` suite —
**3/9 pass**; the other 6 fail on TabPFN-3's CPU >1000-sample guard (a
hardware limit, not a messy-data robustness gap — the ≤1000-row tasks pass
cleanly). Override via `ignore_pretraining_limits` /
`TABPFN_ALLOW_CPU_LARGE_DATASET`, or use a GPU / `TabPFNClient`. Full detail
in `docs/frameworks/tabpfn.md`.

**State as of 2026-07-31: Phases 0-7 are all done, and SapientML — the
last un-built framework in the original v1 roster — is now verified
too.** All of Phase 3+4 verified (AutoGluon, TPOT, H2O AutoML, TabPFN —
the last pivoted to a hosted-API client mid-project). **Phase 5 (Tier 2)
is complete**: NaiveAutoML skipped (confirmed-upstream bug, user's call),
LightAutoML/FEDOT/GAMA all verified — GAMA in particular came up clean
despite being health-flagged and time-boxed going in. **Phase 6 closed
out three items** in one pass: AutoGluon's CPU-only torch wheel fix, a
client-side HTTP timeout for openml-python calls, and the `--task` CLI
flag — full writeup below. **Phase 7 (docs finalization)**, 2026-07-30 —
a full sweep of every doc file found and fixed real staleness: a broken
`mkdocs.yml` nav link, `docs/reference/cli.md` missing the `--task` flag,
`NOTICE.md`'s provenance ledger still listing 8 already-built frameworks
as "not yet built," `docs/frameworks/naiveautoml.md` still saying
"blocked" when the user had already decided to skip it, and stale
phrasing/no-status framework lists in `README.md`/`docs/index.md`. Full
list below.

**SapientML verified 2026-07-31** — un-skipped in an earlier session (the
user wanted it added, just not immediately), then actually built out this
session: AMLB's four "extending the benchmark" docs read and distilled
first (the standing gate), a real correction made along the way (a real
AMLB reference implementation exists after all — earlier notes claiming
otherwise were wrong), three install-time bugs found and fixed (a
Python-3.13-incompatible `tantivy` pin, an undeclared `nest_asyncio`
dependency, a scipy-internal regression), and one `exec.py`-level bug
(`predict_option` has to be forced to `"default"` or SapientML silently
changes `predict()`'s output shape for probability-needing metrics). Full
writeup, live-verified API research, and the complete build log are in
`docs/frameworks/sapientml.md` — see the dedicated paragraph further down
for the condensed version. **This closes out the entire original
11-framework v1 roster** (10 verified, NaiveAutoML skipped) — no phase
number was assigned to this work since v1 itself was already closed out
before SapientML was un-skipped. Phases 0-2 are long since complete. The Phase-2 VPS
was deleted by the user; a replacement was provisioned 2026-07-26 (same
specs: 4 vCPU/7.8GB RAM/232GB disk, new IP — see
`docs/operations/.vps-access.local.md`) via `scripts/provision_vps.sh`,
which went green first try.

AutoGluon's manifest/`exec.py` (drafted 2026-07-21, committed 2026-07-26 in
`57a94b3`) installed cleanly on it. The smoke test was then blocked for
~3 days on an OpenML API outage (their `/api/v1/xml/task/*` endpoint went
fully unresponsive, confirmed external — see `STATUS.md`'s Notes for the
historical record); once OpenML recovered on its own 2026-07-29, `caml run
AutoGluon --benchmark test --constraint test` completed cleanly with real,
plausible scores on all 6 jobs, and `tests/test_e2e_framework_run.py`
passed too. `STATUS.md`'s AutoGluon row is now `verified`, and
`docs/frameworks/autogluon.md` has the real gotchas — most notably a
confirmed **upstream** AutoGluon 1.5.0 bug (its own `fastai`/`fastcore` pin
combo breaks the NeuralNetFastAI model on every job; AutoGluon's own
exception handling routes around it automatically, so it doesn't affect
correctness, just means that one model type never contributes). Not fixed
by us — would mean overriding AutoGluon's own dependency spec, flag to the
user before touching it.

**TabPFN's original local-package attempt (`tabpfn==8.1.0`) was BLOCKED
on a licensing gate 2026-07-29** — `post_install_script` failed because
TabPFN 8.1.0 requires a one-time Prior Labs account + license acceptance
(at ux.priorlabs.ai) before it'll serve model weights at all, even
non-interactively, and account creation/license acceptance weren't ours
to do on the user's behalf. **Resolved and verified 2026-07-30**: the user
registered, accepted the license, created an API key, and asked to pivot
to Prior Labs' hosted `tabpfn-client` instead of the local `tabpfn`
package — `fit()`/`predict()` now call Prior Labs' API over HTTPS rather
than running a local model, authenticated via a `TABPFN_TOKEN`
environment variable (see `docs/operations/tabpfn-access.md` for the
storage convention — untracked, gitignored, never committed;
`frameworks/TabPFN/exec.py` fails fast with a clear error if it's unset).
This sidesteps the weight-download gate entirely but is a real
architectural change, not just an implementation swap — see the
license-flags section below for the external-data-transmission
implication. Installed and smoke-tested cleanly on the VPS on the first
attempt after the pivot (kc2 AUC 0.859/0.910, iris acc 1.000/1.000,
cholesterol RMSE 43.42/54.07) — see `docs/frameworks/tabpfn.md`.

**NaiveAutoML (Phase 5, first Tier-2 framework attempted) hit a real,
confirmed-upstream bug that fails every task type — needs a decision, not
something to route around unilaterally.** Drafted against the current
`naiveautoml` API (found and fixed one real port bug along the way: AMLB's
`max_hpo_iterations=1e10` is a float, but current `naiveautoml` does
`range(self.task.max_hpo_iterations)` internally, which needs an int —
independently corroborated by github.com/fmohr/naiveautoml issue #75,
someone else hit the exact same thing running NaiveAutoML under AMLB with
short time constraints). After that fix, install and smoke-test still
fail on **every** task in the test benchmark (kc2, iris, cholesterol —
not dataset-specific) with `KeyError: nan` inside `naiveautoml`'s own
`fit()` method (`get_config_space_for_selected_algorithms`, looking up
`self.config_spaces[step][selection]` where `selection` is NaN).
Diagnosed down to the root cause: `naiveautoml.py`'s
`as_result_for_best_candidate` is built from the single
globally-highest-scoring row across its *entire* per-phase evaluation
history, not from a row that actually corresponds to the final decided
combination of pipeline steps — if that single best-scoring row happens
to come from an early, single-step evaluation phase, other steps'
`_class` columns are NaN in that specific row, and the later lookup
crashes. Reproduced consistently across two independent runs (kc2 twice,
each hitting a different code path — `KeyError: nan` directly, and
separately during HPO) and confirmed via GitHub issue search that this is
a known class of problem for AMLB-style short-time-budget integrations,
not something specific to CAML's port. **User's call (2026-07-30): skip
it**, same treatment as SapientML — not load-bearing for the project.

**SapientML verified 2026-07-31 — the last framework in the original
11-framework v1 roster, now fully built.** Un-skipped in an earlier
session (the user wants it added, not dropped), and this session actually
built it out end to end. AMLB's four official "extending the benchmark"
docs were read and distilled first — see `docs/frameworks/sapientml.md`'s
Part 1, which maps each AMLB concept to its CAML equivalent (most of it
is machinery CAML already replaced; the load-bearing part is that the
`run(dataset, config)`/`result()` contract is preserved ~verbatim). That
closed the standing gate that had been blocking this framework.

**Correction to a claim this file and `STATUS.md` both had wrong**: prior
sessions stated SapientML has "no confirmed working AMLB reference
implementation." False — verified by actually reading the files.
`automlbenchmark-reference/frameworks/SapientML/exec.py` is a real,
working-looking ~90-line implementation, and the SapientML team
maintains their own AMLB fork (`github.com/sapientml/automlbenchmark`)
with a near-identical one. Both are unpolished (one has a real `=`-vs-`==`
bug) and target a possibly-stale API, so neither was ported blindly — but
"no reference to port from" was never true.

Bringing it up on the real VPS found and fixed four real bugs, three
install-level and one in `exec.py`:
1. **`tantivy` has no Python 3.13 wheel.** `sapientml`'s own pin
   (`tantivy<0.22,>=0.21`) locks in `tantivy==0.21.0`, which only ships
   manylinux wheels up to cp312, and its sdist fails to build under uv's
   stricter PEP 621 metadata checks — same class of fix as LightAutoML's
   `statsmodels` pin and FEDOT's `scipy` pin: `[python].range` capped at
   `<3.13`.
2. **`nest_asyncio` is a genuine undeclared upstream dependency** —
   `sapientml/executor.py` does a bare `import nest_asyncio`, but neither
   `sapientml==0.4.17` nor `sapientml-core==0.8.0` lists it in
   `Requires-Dist` (checked both via PyPI's JSON API). Added explicitly.
3. **A scipy-internal regression, triggered by `sapientml-core`'s own
   loose `scipy<2.0,>=1.14.0` pin.** The default resolution (scipy
   1.18.0) breaks a completely standard `scipy.stats.kstest(...)` call
   inside `sapientml_core`'s meta-feature code with `TypeError: ndtr()
   takes from 1 to 2 positional arguments but 3 were given` — reproduced
   in total isolation (no SapientML involved) to confirm this is a
   scipy-internal issue, not an integration bug. Fixed with a
   `scipy==1.14.1` steering pin (the floor of `sapientml-core`'s own
   allowed range, confirmed working against the same isolated repro).
4. **`predict_option` must be forced to `"default"`.** Left at
   SapientML's own default (`None`), a probability-needing
   `adaptation_metric` (auc/logloss/ROC_AUC/Gini/MAP_K) makes SapientML
   select a pipeline whose `predict()` output *shape* changes entirely —
   observed both raw probability floats where a hard label was expected
   (kc2, metric `auc`) and a `KeyError` because the target column wasn't
   even present in the output (iris, metric `logloss`). `exec.py` now
   forces `predict_option="default"` via `training_params.setdefault(...)`
   (still overridable through `framework_params`) to keep the output
   shape predictable regardless of which metric is requested.

After all four fixes: a clean 6/6 smoke test, real plausible scores in
line with every other verified framework — kc2 AUC 0.668/0.861, iris acc
0.933/1.000, cholesterol RMSE 46.57/54.42 — total wall-clock 85 seconds.
Full research writeup, live-verified current `SapientML`/`SapientMLConfig`
API, the CAML-metric-to-`adaptation_metric` translation table, and the
complete chronological build log are all in `docs/frameworks/sapientml.md`
— now the primary reference for this framework, not just a placeholder.
The user is also still open to suggesting further frameworks beyond the
original 11-framework v1 roster ("if you know any other great autoML
like these, let me know"), with an explicit ask to stay consistent with
how frameworks are added here — not urgent, no specific framework
proposed yet.

**LightAutoML verified 2026-07-30 — Phase 5's second framework attempted,
first to land.** Unlike TPOT/NaiveAutoML, verifying live against
`github.com/sb-ai-lab/LightAutoML` found no breaking API drift from
AMLB's reference at all — ported closely. One real install bug: its
`statsmodels<=0.14.0` dependency pin has no prebuilt wheel for Python
3.13 (lightautoml's own classifiers claim 3.8-3.13, but that's
misleading once a sub-dependency's actual wheel availability is checked),
so the first install attempt fell back to a source build that failed on
a Cython compile error. Fixed by capping `[python].range` at `<3.13`.
After that, install and the full smoke test went cleanly — kc2 AUC
0.870/0.884, iris acc 1.000/1.000, cholesterol RMSE 42.50/54.54. Full
detail, including a non-blocking kc2 balanced-accuracy observation and a
one-off TPOT E2E timing flake unrelated to LightAutoML (test benchmark's
real per-task budget is 60s, not the 600s constraint ceiling — see
`STATUS.md`), in `docs/frameworks/lightautoml.md`.

**GAMA verified 2026-07-30 — Phase 5's fourth and final framework this
pass, closing out Phase 5.** The health-flagged, time-boxed entry in the
roster (last PyPI release 2024-06-14, last GitHub push 2024-09-04, both
re-confirmed live immediately before starting, over two years stale by
this point) — came up clean well within the timebox, no need to escalate
to the user for a best-effort-downgrade call. Also surfaced a real
discrepancy in GAMA's own metadata: its `pyproject.toml` declares
`license = {text = "MIT"}`, but the actual `LICENSE` file at the repo
root is Apache License 2.0 (confirmed both via GitHub's own license
detection and reading the file directly) — an inconsistency in the
upstream project itself; treated the actual `LICENSE` file as
authoritative, matching this project's existing Apache-2.0
classification. Two real install bugs found and fixed, zero `exec.py`
bugs: a `numpy<2` steering pin (GAMA's own `scikit-learn<1.3` pin
resolves to `scikit-learn==1.2.2`, which predates numpy 2.0 and whose
compiled extensions crash on import against a numpy 2.x runtime — same
class of fix as H2OAutoML's identical pin, third framework needing it),
and a `setuptools<82` steering pin (GAMA's `stopit` sub-dependency — the
*same* `stopit` package that caused TPOT's original instance of this bug
— does a bare `import pkg_resources`, third framework needing this exact
fix). After both: all 6 test-benchmark jobs produced real, plausible
scores (kc2 AUC 0.890/0.887, iris acc 0.933/1.000, cholesterol RMSE
42.14/53.96). Full detail in `docs/frameworks/gama.md`.

**FEDOT verified 2026-07-30 — Phase 5's third framework attempted, second
to land clean with only an install-level fix.** Verified live against
`github.com/aimclub/FEDOT` (tag `v0.7.5`) *before* writing any code, same
discipline as LightAutoML: despite FEDOT being far more actively
developed than TPOT/NaiveAutoML (both of which had real breaking API
drift), the `Fedot` class surface AMLB's reference `exec.py` uses was
completely unchanged — including a non-obvious bit worth having actually
checked: `metric`/`max_pipeline_fit_time`/`preset` aren't named
constructor parameters (they flow through `**composer_tuner_params` into
`ApiParams`, which raises `KeyError` on any unrecognized key), and all
three are still in its allowlist. One real install bug found and fixed —
same class as TPOT's `setuptools<82` pin (a bare `import pkg_resources`
inside FEDOT's `hyperopt` sub-dependency fails on a bare `uv venv` +
current setuptools) — FEDOT is the *second* framework in the roster to
need this exact fix. Also confirmed empirically: `fedot`'s own
`scipy<1.13.0` pin has no cp313 wheel, so `[python].range` is capped at
`<3.13`, same class of fix as LightAutoML's `statsmodels` pin. After both
fixes, all 6 test-benchmark jobs produced real, plausible scores (kc2 AUC
0.846/0.873, iris acc 0.933/1.000, cholesterol RMSE 42.57/53.67). Full
detail in `docs/frameworks/fedot.md`.

**TPOT verified 2026-07-30 — rewritten from scratch against the current
(post-2025-rewrite) API, not ported from AMLB's reference**, which targets
the old API and doesn't run as-is (`config_dict=`→`search_space=`,
`scoring=`→`scorers=`/`scorers_weights=`, `evaluated_individuals_`→
`evaluated_individuals`; full diff in `docs/frameworks/tpot.md`). Bringing
it up found and fixed three real bugs, one of them general (not
TPOT-specific): `src/caml/frameworks/installer.py` wasn't shell-quoting
package specs before building the `uv pip install` command, which broke
on TPOT's `setuptools<82` pin (the first non-`==` pin in the roster) —
fixed with `shlex.quote()`, would have bitten any future framework needing
one. The other two (a `pkg_resources`/setuptools steering pin, and
`tpot.classes_` label-mapping — TPOT's `.predict()` doesn't round-trip in
the original label space, unlike every other framework here) are
TPOT-specific, documented in `docs/frameworks/tpot.md`. All 6 test-jobs
now produce real scores in line with every other verified framework.

**H2O AutoML verified 2026-07-30 — Phase 4 done, first-try clean install
and run, zero bugs found** (a first for this roster; AutoGluon and TPOT
each surfaced real bugs). The first framework with a runtime dependency
outside Python itself (`h2o.init()` spawns a local `java` child process)
and the first needing an apt system package (`openjdk-17-jre-headless`).
Two real H2O-3 constraints went into `framework.toml` after verifying live
against `docs.h2o.ai` (not visible from a bare `pip install h2o`): the
Python client only documents support up to 3.11 (pinned `<3.12`, unlike
every other Tier-1 framework so far), and H2O-3 requires `numpy<2` (added
as a steering pin, same class of fix as MLJARSupervised's `numba>=0.60`
and TPOT's `setuptools<82`). Both the apt-install path
(`installer.py::_ensure_apt_packages()` + the `caml` user's NOPASSWD
sudoers entry) and `caml doctor`'s `pgrep -f h2o.jar` stray-JVM check —
both written speculatively in Phase 0 — worked correctly the first time
they were actually exercised. All 6 test-benchmark jobs produced real,
plausible scores (kc2 AUC 0.866/0.873, iris acc 1.000/1.000, cholesterol
RMSE 45.47/54.72) in line with every other verified framework, and no
orphaned JVMs remained afterward. Full detail in `docs/frameworks/h2o.md`.

**Phase 6 (cross-cutting hardening) verified 2026-07-30 — all three known
candidate items closed in one pass, no new bugs found in the existing
roster.**

1. **AutoGluon's CPU-only torch wheel fix** — added the same
   `extra_index_urls = ["https://download.pytorch.org/whl/cpu"]` fix
   already proven for LightAutoML. Verified on the real VPS after
   `caml uninstall AutoGluon && caml install AutoGluon`: `torch ==
   2.9.1+cpu`, `torch.version.cuda is None`, zero `nvidia-*` packages
   pulled. Re-ran the full smoke test post-reinstall — all 6 jobs
   produced scores identical to the pre-fix run (kc2 AUC 0.853/0.932,
   iris acc 0.933/1.000, cholesterol RMSE 44.16/54.65), confirming the
   wheel swap is disk/bandwidth-only. See `docs/frameworks/autogluon.md`.
2. **`openml-python` client-side timeout gap** — closed via
   `src/caml/benchmarks/openml.py::install_default_http_timeout()`,
   which patches `requests.Session.request` to apply a 120s default
   whenever a caller doesn't specify one, called once at that module's
   import time. That module is orchestrator-only (never imported inside
   a framework's isolated subprocess venv — `frameworks/shared/callee.py`
   only imports from `caml.utils`), so this can't break a framework venv
   that lacks `requests`. **Non-obvious finding worth remembering**:
   `socket.setdefaulttimeout()` does **not** rescue this — empirically
   confirmed (a hung local-socket test still hung past a 15s wall-clock
   guard with `socket.setdefaulttimeout(2)` set) that `requests`/`urllib3`
   ignore the socket-level default entirely when no explicit `timeout=`
   kwarg is passed; patching `requests.Session.request` directly is the
   only reliable fix, and is the workaround `requests`' own maintainers
   point to (https://github.com/psf/requests/issues/3070). Covered by a
   real regression test (`tests/test_openml_http_timeout.py`) using an
   actual hung TCP listener, not a mock — asserts both that an
   unspecified timeout now fails fast and that a caller-supplied timeout
   still wins over the default (so a legitimately slow dataset download
   isn't cut short).
3. **CLI task/fold-scoping flag** — actually already done (the `--task`
   flag landed right at the Phase 5→6 boundary, commit `e2213bf`); this
   entry just closes the loop since this file's text hadn't caught up.
   `caml run <name> --task <task> --fold <n>` scopes to one job instead
   of the full benchmark matrix — verified end-to-end on the VPS.

All three changes were re-verified together via a full `pytest tests/`
run (unit + manifest + the new HTTP-timeout test + the 7-framework
`test_e2e_framework_run.py` E2E suite) on the real VPS after a fresh
`git archive` sync — see `STATUS.md` for the pass/fail tally.

**Phase 7 (docs finalization) done, 2026-07-30** — read every doc file in
the repo (`docs/**`, `README.md`, `NOTICE.md`, `mkdocs.yml`) looking for
staleness against the now-complete Phase 0-6 work, rather than assuming
the docs had kept pace. Found and fixed six real issues:

1. `mkdocs.yml`'s nav referenced `frameworks/h2o-automl.md`; the real
   file is `frameworks/h2o.md` — a broken nav link.
2. `docs/reference/cli.md` documented `caml run`'s `--fold` flag but not
   `--task` (added Phase 6) at all.
3. `NOTICE.md`'s provenance ledger was the most substantively stale: its
   "Framework integrations ported ~verbatim" table only covered
   FLAML/MLJARSupervised, and its closing "Not ported" section still
   listed 8 frameworks (AutoGluon, TabPFN, TPOT, H2OAutoML, LightAutoML,
   FEDOT, NaiveAutoML, GAMA) as "not yet built" when all 8 were actually
   built (7 verified, NaiveAutoML built-then-skipped) — only SapientML is
   genuinely unbuilt. Added proper entries across four categories:
   ported-~verbatim (FEDOT, LightAutoML), ported-with-modification
   (AutoGluon, H2OAutoML, NaiveAutoML, GAMA — each with what actually
   changed), rewritten-entirely (TPOT, whose AMLB reference targets a
   superseded pre-2025-rewrite API), and no-AMLB-precedent (TabPFN, which
   has no AMLB directory to port from at all).
4. `docs/frameworks/naiveautoml.md`'s status field still said **blocked**
   and its closing paragraph described the skip/time-box/file-upstream-issue
   decision as still pending — the user had already decided to skip it
   (see the NaiveAutoML paragraph above). Updated to **skipped** with the
   actual resolution.
5. `README.md`'s Quickstart heading still said "(once Phase 1+ lands)" —
   stale since Phase 1, let alone Phase 6. Both `README.md` and
   `docs/index.md` listed all 11 roster frameworks with no indication
   NaiveAutoML is skipped or SapientML isn't built — added a one-line
   status summary to both, pointing to `STATUS.md` for live detail.
6. Added a Phase 6 entry to `docs/operations/troubleshooting.md`'s
   durable-knowledge log for the `openml-python`/`socket.setdefaulttimeout()`
   finding — this file's whole purpose is exactly this kind of lesson.

Deliberately did **not** touch: the four AMLB "extending the benchmark"
docs (still explicitly deferred, tied to SapientML's revisit or any
framework beyond the current 11, not part of finalizing docs for the
*existing* roster) or anything SapientML-shaped (still deferred, not
next up). Re-ran the local test suite after the changes (all doc edits,
zero code touched) — still 15 passed.

**v1's entire original 11-framework roster is now feature-complete,
verified, and fully documented** — 10 verified (AutoGluon, H2O AutoML,
FLAML, MLJAR-supervised, TabPFN, TPOT, LightAutoML, FEDOT, GAMA,
SapientML), NaiveAutoML skipped on a confirmed-upstream bug.
**Immediate next step for a new session**: no phase or framework is
actively in progress. Standing open items, none urgent: (a) the user's
standing open invitation to suggest further AutoML frameworks beyond the
original 11-framework roster, with an explicit consistency requirement —
no specific framework proposed yet; (b) Phase 8 backlog (GPU
auto-detection, version-check bot, report/upload parity, more
frameworks) — explicitly not v1. See the roster table's per-framework
notes for other known risk factors on frameworks already done.

`tests/test_e2e_framework_run.py` (added mid-project): a real pytest test
(parametrized over whatever frameworks are actually installed, auto-skips
if none are) that runs a framework for real and asserts non-NaN scores —
codifies the runbook's manual smoke-test step. Validated repeatedly
against every verified framework on the VPS, most recently all 8
installed frameworks passing together (AutoGluon, FEDOT, GAMA, H2OAutoML,
LightAutoML, TPOT, TabPFN, SapientML) — see `STATUS.md`.

Phase 3 order: AutoGluon (done) → TPOT (done) → TabPFN (done — Phase 3
shipped the hosted client; local `tabpfn` added + made the primary `TabPFN`
2026-07-31, hosted entry renamed `TabPFNClient`) → Phase 4 (H2O, done) → Phase 5 Tier 2, now fully done
(NaiveAutoML skipped → LightAutoML done → FEDOT done → GAMA done) → Phase
6 (cross-cutting hardening, done) → Phase 7 (docs finalization, done) →
SapientML (un-skipped, then verified 2026-07-31, no phase number). v1's
entire original roster is done; no phase is next until new scope is
added (e.g. a further-framework suggestion, or Phase 8). Full rationale
in `STATUS.md`.

To get onto the VPS: source connection details from
`docs/operations/.vps-access.local.md`; the working directory there is
`~caml/caml-workspace/CAML`, and framework work runs as the `caml` user
(`sudo -iu caml bash -lc '...'`), never root. **Policy, 2026-07-26: no more
local installs, period** (see "Local vs. VPS work" below, now actually in
effect, not just stated) — writing a new framework's `framework.toml` +
`exec.py` is still done locally (it's just text), but `caml install` and
everything downstream (smoke test, iteration) now always happens on the
VPS, even for pure-pip Tier-1 frameworks like AutoGluon. This supersedes
the Phase 1 pattern where FLAML/MLJAR were installed and verified locally
first, then re-verified on the VPS in Phase 2 — that double-install step
is gone going forward.

## What CAML is

An open-source (Apache-2.0 from v1.0.0, 2026-10-24; proprietary before), near-100%-automated AutoML benchmark harness for Ubuntu cloud
servers, modernizing OpenML's AutoML Benchmark (AMLB). The user (Ali) was
previously blocked trying to install AMLB manually — dependency conflicts,
years-stale framework pins, brittle shell scripts. CAML fixes the install
system while keeping AMLB's solid core idea: one isolated environment per
AutoML framework, communicating with the orchestrator over a subprocess
stdin/JSON boundary. Documentation is a first-class deliverable, not an
afterthought — every framework needs a docs page, every gotcha needs to be
written down, because this is a multi-session effort with real VPS
iteration and state must survive between sessions.

Full plan history: the approved Claude Code plan file kept outside the repo
(the approved plan this project was built from — has the full research
writeup if something here needs more context).

## Workspace layout (do not change without updating this file)

```
projects/AML/                      # the workspace root (any path)
├── CAML/                          # THIS repo — the product. github.com/A1i-Tabatabaei/CAML (private until the 1.0 release is published)
└── automlbenchmark-reference/     # full clone of github.com/openml/automlbenchmark
                                   # READ-ONLY REFERENCE ONLY. Never `pip install`, never `uv run`,
                                   # never execute anything from inside it. It exists purely so ported
                                   # code can be diffed/attributed against real AMLB source + git blame.
```

Same sibling layout gets reproduced on the VPS during Phase 2.

## Locked architecture decisions (need the user's explicit sign-off to change)

1. **MVP scope = Broader MVP**: all 11 Tier-1 + Tier-2 frameworks in the first pass (not a 6-framework tight MVP). Decided via `AskUserQuestion`, 2026-07-17.
2. **Isolation model = bare-metal venv only.** No Docker/Singularity/AWS runner — AMLB's container support is dropped entirely. Target is a single Ubuntu VPS, not a cluster. Decided 2026-07-17.
3. **Python tooling = `uv`** for both interpreter provisioning (`uv python install`) and venv/package management (`uv venv`, `uv pip install`), replacing AMLB's stdlib `venv` + `pip` + fragile `deadsnakes` PPA. Decided 2026-07-17.
4. **Version-pinning strategy = exact-pin-and-deliberately-bump.** Reject AMLB's implicit `"stable"` = always-`pip install -U`-at-install-time default — that pattern is literally how TPOT's 2025 breaking API rewrite silently broke AMLB's integration. Every `framework.toml`'s `current_pin` is set to whatever's genuinely latest when that framework is brought online, then held deliberately. `caml install <name> --latest` is an explicit one-off escape hatch, never the default path.
5. **FEDOT deviation from AMLB**: pin to latest PyPI release, not git `master` (AMLB's `resources/frameworks.yaml` tracks FEDOT's git `master` HEAD today — zero reproducibility, explicitly not repeated here).
6. **Manifest format = TOML** (`framework.toml`), not YAML. Stdlib `tomllib`, no extra dependency, avoids the indentation-sensitivity that already causes subtle bugs in AMLB's own `frameworks.yaml` `params` blocks.

## Framework roster (v1 = 11 frameworks)

See `STATUS.md` for **live** per-framework install/verification status — this table is roster *rationale*, not live state.

| Framework | Tier | License | System deps | Notes |
|---|---|---|---|---|
| FLAML | 1 | MIT | — | Simplest — build first as the plugin-contract reference implementation |
| MLJAR-supervised | 1 | MIT | — | Second reference implementation |
| AutoGluon | 1 | Apache-2.0 | — | Pure pip, largest dep tree |
| TabPFN | 1 | Apache-2.0 code; **weights non-commercial** (local OSS `tabpfn`, 2026-07-31 — see license flags below) | none (CPU torch wheel) | **No AMLB precedent — `exec.py` built from scratch**; runs on-box, 1-time license + `TABPFN_TOKEN` for weight download |
| TabPFNClient | 1 | Apache-2.0 (hosted `tabpfn-client` — data leaves the box, see license flags below) | none (server-side compute) | hosted-API sibling of `TabPFN`; was the original `TabPFN`, renamed 2026-07-31 |
| TPOT | 1 | LGPL-3.0 | — | **`exec.py` must be rewritten**, not ported — see "TPOT API break" below |
| H2O AutoML | 1 | Apache-2.0 | JRE (openjdk-17) | JVM subprocess — see "H2O JVM lifecycle" below |
| LightAutoML | 2 | Apache-2.0 | torch (CPU wheel) | Heavy deps; verify Python 3.11–3.13 empirically |
| SapientML | 2 | Apache-2.0 | lancedb/tantivy/mecab-python3 (all pure pip, confirmed zero apt) | Verified 2026-07-31 — real (if unpolished) AMLB reference existed after all, see `docs/frameworks/sapientml.md` |
| FEDOT | 2 | BSD-3-Clause | — | Pin latest PyPI, not git master (deviation from AMLB, see above) |
| NaiveAutoML | 2 | MIT | — | Exact-pins `numpy<2`, `scikit-learn==1.5.2`, `configspace==1.2.0` as of 2026-07-17 — the clearest real-world case for per-framework venv isolation in the whole roster |
| GAMA | 2 | Apache-2.0 (its own `pyproject.toml` says MIT — a real upstream metadata discrepancy, see "GAMA health" below) | — | Was **provisional**, verified 2026-07-30 — see "GAMA health" below |

**Explicitly excluded from v1** (confirmed dead/archived/stalled/wrong-ecosystem as of 2026-07-17): auto-sklearn / auto-sklearn2 (stalled 3+ yrs at v0.15.0, capped at Python≤3.9, needs swig compile), Auto-PyTorch (abandoned), NNI (archived by Microsoft Sep 2024), EvalML (stalled), AutoWEKA, ML-Plan/MLPlan (dead jar download endpoint), MLNet (.NET runtime, EOL .NET Core 3.1), mlr3automl (R, dead), oboe (dead since 2021), hyperopt-sklearn, autoxgboost (R). Ludwig/AutoKeras excluded (DL/NAS-focused, heavy GPU footprint, poor fit for pure tabular classification/regression) — revisit only if scope expands beyond tabular.

## Research findings that ground every fix (verified live 2026-07-17 against AMLB's actual source, PyPI, and each framework's own repo — not training-data memory)

- AMLB's own root `requirements.txt` hard-pins `numpy==1.24.2` — no Python 3.12 wheel, needs removed `distutils`. On Ubuntu 24.04's default Python 3.12, installing the *orchestrator itself* fails before touching any framework. CAML uses flexible modern ranges instead (see root `pyproject.toml`).
- `deadsnakes` PPA dependency (AMLB's Docker/Singularity templates) — irrelevant in CAML, `uv python install` manages interpreters directly, no apt/PPA at all.
- `openjdk-8-jdk` hardcoded in AMLB's H2O/AutoWEKA `setup.sh` — Java 8 packages aren't in Ubuntu 24.04's default archives. CAML uses `openjdk-17-jre-headless`.
- **TPOT API break**: TPOT's 2025 ground-up rewrite (merged into mainline `tpot` as v1.x) removed the `config_dict=` constructor kwarg AMLB's `TPOT/exec.py` still uses, and renamed `evaluated_individuals_` (dict) to `evaluated_individuals` (DataFrame, no trailing underscore). CAML's `frameworks/TPOT/exec.py` must call the new API: `TPOTClassifier(search_space="linear", scorers=[...], scorers_weights=[...], max_time_mins=..., ...)`, then read `tpot.evaluated_individuals` (DataFrame) and `tpot.fitted_pipeline_` (unchanged) for predictions.
- AMLB's `frameworks/shared/setup.sh` has a live bug: `if [[ ! -x py_exec ]]` is missing a `$` (should be `$py_exec`) — the "venv already exists" check is always true. Moot once replaced by `installer.py`, but a signal this codebase needs verification, not blind trust.
- **The isolation mechanism worth preserving**: AMLB's `frameworks/shared/caller.py::run_in_venv()` just execs `frameworks/<name>/venv/bin/python` as a subprocess (dataset + `TaskConfig` piped over stdin as JSON, results read back from a file) — it has zero opinion about *how* that venv was created. A `uv venv` at the same path is a drop-in replacement. `caller.py`/`callee.py` are ported ~verbatim; only the venv-creation layer underneath changes.
- **NaiveAutoML** exact-pins `numpy<2`, `scikit-learn==1.5.2`, `configspace==1.2.0` on PyPI today — a hard constraint, not a wheel-availability problem. Strongest live argument in the roster for per-framework isolated venvs.
- **GAMA health flag — resolved 2026-07-30, came up clean.** Last PyPI release `23.0.0.post1` (2024-06-14), last GitHub push to `amore-labs/gama` (renamed from `openml-labs/gama`, originally `PGijsbers/gama`) on 2024-09-04, PyPI listing has no `home_page`/`project_urls`/`author` metadata — all re-confirmed live immediately before the Phase 5 install attempt, still accurate, now over two years stale. Despite the flag, install + smoke-test came up clean well within the time-box: two real bugs (`numpy<2` and `setuptools<82` steering pins, see `docs/frameworks/gama.md`), zero `exec.py` bugs, no need to escalate to the user for a best-effort-downgrade call. Also found a real license-metadata discrepancy: `pyproject.toml` says MIT, the actual `LICENSE` file is Apache-2.0 — treated the file as authoritative. Lesson for future stale/thin-metadata frameworks: the flag is worth raising and time-boxing for, but isn't a reliable predictor of an actual bring-up problem.
- **TabPFN has no usable AMLB reference implementation at all** (no AMLB directory exists upstream), built from scratch against Prior Labs' docs. **SapientML's "no reference" claim (present in earlier versions of this file) was wrong** — a real, if unpolished, `exec.py` exists both in `openml/automlbenchmark` and in the SapientML team's own `sapientml/automlbenchmark` fork; verified live 2026-07-31, see `docs/frameworks/sapientml.md`. Still budget extra time for SapientML — the dependency tree is unusually heavy (catboost/lightgbm/xgboost/numba/lancedb/tantivy/mecab-python3) and the reference targets a possibly-stale API (40+ PyPI releases since the reference was likely written) — but "built from scratch" is no longer accurate for it.
- **H2O JVM lifecycle**: must call `h2o.cluster().shutdown()` in `exec.py`'s `finally` block, covering exception *and* timeout/SIGTERM paths, to avoid orphaned `java` processes accumulating across repeated VPS runs. `caml doctor` should include a `pgrep -f h2o.jar` stray-process check.
- **Torch-pulling frameworks** (LightAutoML, AutoGluon — the latter added in Phase 6, 2026-07-30; and the local `TabPFN`, re-added 2026-07-31) need `extra_index_urls = ["https://download.pytorch.org/whl/cpu"]` in their manifest to force CPU-only wheels on the CPU-phase VPS — avoids multi-GB CUDA wheel downloads now, and is a one-line flip (not a redesign) when the GPU phase arrives. Verified for local `TabPFN`: `torch==2.13.0+cpu` resolved via this exact fix. (The hosted `TabPFNClient` is *not* in this group — it has no torch dependency; all compute is server-side.)
- **`requests` does not fall back to `socket.setdefaulttimeout()`** — a call with no explicit `timeout=` kwarg blocks forever regardless of the socket-level default, confirmed empirically 2026-07-30 while closing the `openml-python` timeout gap (see the Phase 6 writeup above). The only reliable process-wide fix is patching `requests.Session.request` itself. Worth remembering before assuming a socket-level timeout setting protects any future `requests`-based integration in this codebase.
- **FEDOT** PyPI classifiers claim only Python 3.8–3.10, but that's not the real constraint (confirmed live, 2026-07-30): `requires_python` itself is a loose `>=3.8` with no ceiling, and empirically 3.12 works fine. The actual ceiling is transitive — `fedot==0.7.5` hard-pins `scipy<1.13.0`, and the newest matching release (scipy 1.12.0) has no cp313 wheel — so `[python].range` is capped at `<3.13`, same class of fix as LightAutoML's `statsmodels` pin. See `docs/frameworks/fedot.md`.
- **AMLB itself confirmed MIT** (Copyright (c) 2018 OpenML) — fetched verbatim from `raw.githubusercontent.com/openml/automlbenchmark/master/LICENSE` on 2026-07-17, stored at `THIRD_PARTY_LICENSES/AMLB-LICENSE.txt`. Safe to port/vendor code with standard attribution (see `NOTICE.md`).

## Phase 1 findings (bringing up FLAML + MLJAR-supervised, 2026-07-18)

Both reference frameworks are now verified end-to-end (real non-NaN scores) in the dev sandbox. Six real bugs surfaced and were fixed — full writeups in `docs/operations/troubleshooting.md` and `NOTICE.md`; the two worth knowing before touching anything import-related:

- **`caml/__init__.py` must stay lazy (PEP 562 `__getattr__`), not eager like AMLB's `amlb/__init__.py`.** Every framework's `exec.py` runs inside its own minimal venv (just `frameworks/shared/requirements.txt`) and imports the leaf module `caml.utils`. Importing any submodule always executes the parent package's `__init__.py` first — so an eager `from .resources import Resources` there (which chains into `caml.benchmarks.openml` → `import openml`) crashes *every* framework subprocess, since `openml` is never installed into a framework's own venv. Don't add eager heavy imports back to `caml/__init__.py`.
- **`frameworks/shared/caller.py`'s subprocess `PYTHONPATH` needs two entries**, not AMLB's one: `<root>/src` (for `caml.*`, since CAML uses a src-layout) *and* `<root>` (for `frameworks.*`, which stays at the repo root as `src/`'s sibling). Both `caml.utils` (via `frameworks/shared/utils.py`) and `frameworks.shared.callee` (via every `exec.py`) need to resolve inside the subprocess.
- Modern-library compatibility gaps found (numpy 2.0, pandas 2.0, pandas 3.0's Arrow-backed string dtype) are exactly the class of problem this whole project exists to catch — expect more of these as Tier 1/2 frameworks come online, especially anything touching string-labeled prediction columns (the `ArrowStringArray` fix in `serialization.py` is centralized and should cover most of them, but watch for it).
- Working directory drift (an earlier `cd` into `automlbenchmark-reference/` for research left later commands running from the wrong directory, producing confusing "wrong venv"/"wrong Python" symptoms) cost real debugging time — always `cd` explicitly into the CAML repo root before `uv run`/`caml` commands.

## Phase 2 findings (real VPS bring-up, 2026-07-21)

Provisioned a fresh Ubuntu 24.04 VPS (4 vCPU / 7.8GB RAM / 232GB disk) and re-verified FLAML + MLJAR-supervised end-to-end on it. The headline is that **nothing in the code broke** — the Phase-1 modern-library fixes were exactly the right ones, and the real box behaved identically to the dev sandbox. The lessons are about *provisioning*, not the orchestrator:

- **A fresh VPS has no GitHub credentials, so `git clone <private CAML repo>` (as `vps-bootstrap.md` originally instructed) just fails.** This was the one real "100% automation" gap. Fixed by delivering the repo as a pushed `git archive` of `HEAD` over the existing SSH connection — no credential ever lands on the box. Implemented in the two new scripts below. If a git-based flow is ever wanted (so the box can `git pull`), provision a read-only deploy key out of band and set `CAML_SRC` to the SSH URL — `setup_workspace.sh` supports it; it's just not the default.
- **Two new provisioning scripts, both tested on the real instance** (cold path + idempotent re-run):
  - `scripts/setup_workspace.sh` — runs as the `caml` user; reproduces the sibling workspace layout, `uv sync`, `caml doctor`. Idempotent. Env knobs: `WORKSPACE_DIR`, `CAML_SRC` (archive path *or* git URL), `CAML_REPO_URL`, `AMLB_REF_URL`.
  - `scripts/provision_vps.sh` — operator-side one-shot: `git archive` push → `bootstrap_vps.sh` as root → `setup_workspace.sh` as `caml`. Assumes working SSH (key-based/`~/.ssh/config`); transport is overridable via `SSH=`/`SCP=` env vars for non-standard auth. `scripts/provision_vps.sh root@<host>` takes a fresh box to a green `caml doctor` in one command.
- **Benign, non-blocking observations** (recorded, deliberately *not* fixed):
  - FLAML and MLJAR both pull `nvidia-nccl-cu12` (~289MB) transitively via xgboost's Linux wheel — unused on a CPU box, pure disk/bandwidth cost. Left as-is; the CPU-index treatment reserved for the *torch*-pulling frameworks (see the torch note above) could be extended to xgboost later if disk pressure appears, but it's a one-line manifest change, not worth doing speculatively.
  - The per-fold "Metric scores" debug dict logs `duration: nan`; the aggregated `output/results.csv` carries the real per-job durations (job-level duration is attached *after* that log line). Cosmetic, not a data bug — don't chase it.
- Non-project tooling gotcha for whoever automates this next: `rsync`ing a file into a not-yet-existing remote directory fails (rsync won't create intermediate dirs for a file dest) — `mkdir -p` the remote dir first, or rsync a trailing-slash directory. Cost a retry during Phase 2.

## License/legal flags (non-blocking today, revisit if scope changes)

- **TPOT is LGPL-3.0** — standard "installed as a dependency in its own venv, not modified/embedded" usage, fine for internal/proprietary use as-is.
- **TabPFN is offered in two variants (2026-07-31), each with its own license story:**
  - **`TabPFN` (local OSS `tabpfn`)** runs on-box, so no data-egress concern — but the **TabPFN-3 model weights are under a non-commercial license** (the `tabpfn` code itself is Apache-2.0-based, the "Prior Labs License"). Fine for CAML's internal benchmarking on public OpenML data; **get a real legal read before any CAML result that used this framework leaves internal use.** Needs a one-time Prior Labs license acceptance (the TabPFN-3 model license) to download weights — a user action, done 2026-07-31.
  - **`TabPFNClient` (hosted `tabpfn-client`)** is Apache-2.0 and needs no weight download, but **sends training/test data to Prior Labs' servers**, unlike every other framework here (which runs 100% locally). The "internal benchmarking... without external communication" exemption reasoning doesn't apply to it verbatim — it does external communication by design; not a problem for internal-only use against public data, just no longer the reason it's fine. Don't point it at anything sensitive.
  - History: the client was built 2026-07-30 when the local package looked blocked on a license gate; that turned out to be resolvable (the user accepted the model license), so the local `TabPFN` was added and became primary, and the hosted entry was renamed `TabPFN` → `TabPFNClient`.
- **CAML's own `LICENSE`**: Apache-2.0 since 2026-10-24 (v1.0.0), replacing
  the proprietary placeholder, with an Apache `NOTICE` file crediting AMLB
  (MIT). Confirmed by Ali on 2026-10-24 (KI-40). The
  frameworks are installed from PyPI at run time and never redistributed,
  so their licenses (TPOT LGPL-3.0, TabPFN-3's non-commercial weights) bind
  the users who run them, not CAML's source license.

## Local vs. VPS work (policy, 2026-07-26; revised 2026-10-21)

**Revision, 2026-10-21 (Ali), withdrawn the same day:** the local
external-drive route failed on the network (OpenML unreachable, slow
downloads), so it's **back to VPS-only**. The withdrawn rule, for the
record: installs and runs allowed on the local laptop, **but only on the
external drive**
`/mnt/MIRC/CAML-STORAGE`. The system disk has about 13GB free and must not
grow. Always go through the deployed workspace (`scripts/sync_local.sh`,
then `source /mnt/MIRC/CAML-STORAGE/caml-env.sh`), never the dev repo. See
`docs/operations/local-storage.md`. The original 2026-07-26 policy below
still applies to the dev repo and system disk:

The local machine has limited disk (`caml doctor` flagged 33.6GB free,
under this project's own 50GB recommendation, even before any Tier-1
framework beyond FLAML/MLJAR was installed). Per the user's explicit
instruction:

- **Never** run `caml install <framework>`, `uv sync` for a new framework's
  deps, or any other package install for an AutoML framework locally.
  Always do this over SSH on a VPS.
- Local work stays fine for anything that doesn't pull new packages onto
  disk: writing/editing `framework.toml` / `exec.py`, code review, docs,
  reading logs, git operations.
- This replaces the earlier Phase-1-era pattern of installing pure-pip
  frameworks locally first as a dry run before the VPS. Don't reintroduce
  that pattern.

## Compute target (GPU by default with CPU fallback — Phase 8, 2026-08-02)

**History:** Phases 0–7 ran deliberately CPU-only (the "verify functionality"
stage — does each framework install and produce correct results at all). GPU
work was held until the whole v1 roster was verified. That gate is passed, the
user replaced the CPU VPS with a **GPU box (RTX A4000)**, and Phase 8 is now
implemented in code (on-box verification pending — see the top handoff).

**The policy is auto-detection, never forcing a GPU.** CAML uses a GPU when the
box has one and falls back to CPU cleanly when it doesn't — no per-run flags.
The full operational reference is `docs/operations/gpu.md`; the design:

- **One override knob, honoured at both install and run time:**
  `CAML_COMPUTE=auto|cpu|gpu` (default `auto`).
- **Install-time (which wheel):** `installer.py::gpu_present()` probes
  `nvidia-smi`; a framework that declares `gpu_extra_index_urls` in its
  manifest installs those CUDA wheels when a GPU is present, its
  `extra_index_urls` (CPU wheels) otherwise. The chosen mode is written to the
  install marker and shown in `caml status`' COMPUTE column.
- **Run-time (which device):** each torch framework's `exec.py` asks
  `frameworks/shared/compute.py::use_gpu()` (via `torch.cuda.is_available()`)
  and sets its own device kwarg. Defensive: no torch / broken driver / a
  `torch.cuda` that raises all resolve to CPU, never a crash.
- **Only the three frameworks with a real GPU code path are wired up:**
  `TabPFN` (`device` → cuda/cpu; **GPU also lifts TabPFN-3's CPU >1000-sample
  guard** — the prime win), `AutoGluon` (`num_gpus=1` → its torch NN / GPU-
  capable GBM models), `LightAutoML` (`gpu_ids="0"`, `CAML_GPU_IDS` overrides).
- **The CPU-bound roster is untouched by design** (FLAML, MLJAR, TPOT, H2O,
  NaiveAutoML, FEDOT, GAMA — all CPU-bound libraries): they declare no GPU
  index, so install and run identically on any box. **Do not** wire GPU into
  them.
- **`TabPFNClient` (hosted) stays exempt entirely** — all its compute is on
  Prior Labs' servers; there is no local inference to accelerate.

**CUDA-version caveat:** the three manifests default to the `cu124` wheel
index. The `cuXXX` suffix must be ≤ the CUDA version the box's driver supports
(top-right of `nvidia-smi`). It's a one-line per-manifest change if a box needs
`cu121`/`cu126`/etc.; a mismatch degrades to CPU rather than crashing. Verify
on the A4000 box and adjust before calling Phase 8 done.

## VPS access

**Never put real host/IP/credentials in this file or any committed file.** Connection details live in an untracked local note only, already `.gitignore`d (verify with `git check-ignore`) — or an SSH config entry outside the repo. See `docs/operations/vps-access.md` for the (credential-free) operational doc.

**Current box (2026-08-02): the GPU box (RTX A4000).** The old CPU box was
deleted by the user; its note (`docs/operations/.vps-access.local.md`) is
stale. The live box's connection details go in the new untracked
`docs/operations/.gpu-vps-access.local.md`. **This box logs in as a non-root
user `administrator` (+ `sudo -i` for root)**, unlike the old direct-`root@`
CPU box — so `bootstrap_vps.sh` runs as `sudo bash bootstrap_vps.sh`, and
`provision_vps.sh` takes `administrator@<host>` (set up key auth first so the
committed no-password scripts work; see the creds file + `docs/operations/gpu.md`).
Work still runs as the `caml` user from `~caml/caml-workspace/CAML`. GPU
specifics (driver check, CUDA wheel index) are in `docs/operations/gpu.md`.

VPS specs to confirm before/at handoff: **≥50GB disk, ≥8GB RAM (16GB+ preferred)** — 11 isolated venvs with largely non-shared heavy deps (torch, lightgbm, xgboost, catboost, sklearn duplicated per-venv by design) plus H2O/AutoGluon/LightAutoML's RAM appetite can plausibly reach 15–30GB+ disk. The Phase-2 box (7.8GB RAM) is right at the floor — the bootstrap's 4G swapfile kicks in below 8GB, which covered FLAML/MLJAR fine, but H2O/AutoGluon/torch frameworks in Phase 3+ will lean on it.

## Meta

Architecture decisions in this file require the user's explicit sign-off to change. No document — including this one — is itself authorization to relitigate the locked decisions above. If you (a future session) think a locked decision is wrong, say so and ask; don't silently drift from it.
