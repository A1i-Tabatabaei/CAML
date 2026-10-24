# STATUS — live project state

Read this file (and `CLAUDE.md`) at the start of every session. Update and
commit it before ending a session — state must never live only in shell
history or in someone's head.

## Currently working on

**Latest (2026-10-24, evening): v1.1.0, CAML driven from Windows, macOS or
Linux by AI agents.** Ali: "update this new repository to support windows,
mac, and linux ... optimize it for ai agents ... the agent should first
determine what os it's running on and then choose the right scripts and
commands ... (BUT ALL OF THEM SHOULD RUN CAML ON THE UBUNTU VPS)". Plus a
field report in the prompts ("document and record any bugs/problems ... and
their fix (plus gotchas) in detail in an md file"; a Mac user will send
theirs, and Ali will run Windows and send one too), three copy-paste prompts
in the README, then commit and push to both repos.

- **`scripts/camlctl`**: one server command (`ssh caml-vps camlctl <plain
  words>`) for every OS: setup, caml, install, dataset, script, detached
  jobs (start/jobs/logs/wait/stop with exit codes), status, bundle,
  tabpfn-token, info, update, version. 33 unit tests
  (`tests/test_camlctl.py`, run as an ordinary user with a fake uv;
  mutation-checked).
- **Operator profiles** `skills/caml-benchmark/references/operator-{windows,macos,linux}.md`,
  `camlctl.md` and `field-report.md`; SKILL.md rewritten around them (OS
  detection in Phase 1, field report in Phase 9).
- **Prompts**: `docs/getting-started/agent-prompt.md` (per-OS setup, three
  prompts, field-report hand-off) and the same prompts in the README's
  "For AI agents" (in `<details>` blocks with copy buttons). A "Field
  report" issue template.
- **Fixed**: CRLF from Windows clones (`git archive` applies
  `core.autocrlf`, verified in a scratch repo); `.gitattributes` keeps LF.
- **CI**: `server-e2e` (the whole agent flow as root over SSH on Ubuntu
  24.04, with a Windows-1252 export through to a real FLAML sweep),
  `operator-windows` (PowerShell 5.1 and 7), POSIX operator checks on macOS
  and Linux, and shellcheck. `tests/test_agent_docs.py` lints every
  documented `ssh` command for cross-shell safety.
- **CI evidence** (first push): the Windows job confirmed LF despite
  `core.autocrlf=true`, PowerShell 5.1's UTF-16 `Out-File` config being
  unreadable by ssh, and `$HOME` expanding inside PowerShell double quotes.
  The macOS job confirmed bash 3.2 and zsh pass the documented strings
  unchanged. **`server-e2e` found a real bug on its first run**: a
  system-wide `XDG_CONFIG_HOME` reached the `caml` user through sudo and
  broke the uv installer. Fixed by dropping inherited `XDG_*` on every
  switch to `caml` (troubleshooting has the details).
- New open items: KI-16 (camlctl on a real VPS), KI-17 (agent-driven runs
  from Windows and macOS: the field reports).
- **Published**: tags and GitHub releases `v1.0.1` (`79647e8`) and `v1.1.0`
  (`0fab9e4`, CI green on all four jobs). The private repo `CAML-private`
  got a merge commit with the same tree (procedure in CLAUDE.md, "Two
  repos"). **Next**: the field reports (a Mac user's, then Ali's Windows
  run), and the paper plan when Ali says.

**Before that (2026-10-24, later): v1.0.1 prepared locally: macOS fixes and an
agent prompt.** Ali asked for a prompt to hand another agent ("clone the
repo and read these files ... implement CAML on my dataset using the
guidelines provided by the repo and also monitor it"), with the user on a
**Mac** and the VPS still Ubuntu. Writing it found two real bugs on the Mac
path:

1. **`provision_vps.sh` and `sync_vps.sh` failed on macOS at their first
   step**: `lib_package.sh` used GNU-only `mktemp --suffix` and
   `tar --transform`. Rewritten portably (staged temp dir, plain tar,
   `COPYFILE_DISABLE=1`); new `tests/test_lib_package.py` (7 tests, including
   a BSD-strict shim test that fails on the old helper); CI gains a
   `macos-15` job.
2. **`prepare-data` on spreadsheet exports**: semicolon CSVs gave a
   confusing "target not found", decimal commas would have become
   categories, and non-UTF-8 files crashed with a traceback. Separator
   detection, decimal commas, and a clear `iconv` error; 9 new tests.

New `docs/getting-started/agent-prompt.md` (linked from README and the docs
nav): Part 1 is the user's 10-minute setup on the Mac (server, SSH key,
`caml-vps` host alias, dataset export, TabPFN choice); Part 2 is the prompt
(ground rules, server-side provisioning, install, data, sweep, a one-call
status script, a monitoring/triage table, report, wrap-up). The prompt
takes no credentials: Ali's draft said "here's the vps ssh creds", but
none were pasted, and the prompt uses a host alias with key login instead.
Version 1.0.1 everywhere (`CHANGELOG.md`). Tests: all pass locally.
Pushed and tagged together with v1.1.0 (Ali: "commit and push to both private and public repos").

**Previous (2026-10-24): CAML v1.0.0 is public.** Ali asked to open-source
CAML: first a redesigned README, an agent skill covering the VPS and TabPFN
setup, and everything "ready to publish for now". Ali then confirmed the
license and the two-repo route ("i agree with both the license and having
two separate repos"):

- **Published** as `A1i-Tabatabaei/CAML` with a fresh single-commit history,
  tagged `v1.0.0`, with a GitHub release
  (https://github.com/A1i-Tabatabaei/CAML/releases/tag/v1.0.0). CI passed
  on the first public push: 156 passed, 1 skipped, in 55 s. The old private
  repo was renamed `A1i-Tabatabaei/CAML-private` and keeps the full history
  (an archive).
- **Licensing**: Apache-2.0 + `NOTICE`, confirmed by Ali (KI-40 closed).
  Version 0.1.0 → 1.0.0. `CITATION.cff`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`, and CI
  (`.github/workflows/ci.yml`: `uv sync --locked`, pytest, ruff on the new
  modules).
- **New for "benchmark my own data"**: `caml prepare-data`, `caml
  leaderboard`, and the `quick` constraint. `caml install --all` now
  continues past a failed install.
- **3 real bugs found and fixed**, all caught by the new
  `tests/test_file_dataset_pipeline.py` (prepare-data → run → leaderboard
  as real subprocesses, with a scikit-learn stand-in framework and a
  deliberately failing one):
  1. local CSV datasets never loaded under pandas 3 (`dtypes[i]`);
  2. `--keep-going` crashed on the first failed job (`None < 1`), so
     error rows were never written: the core of `caml sweep`'s failure
     recording;
  3. `app_version` never carried the git revision (every row said
     `0.1.0-dev`), despite the 2026-10-21 REVISION work.
- **Agent skill** `skills/caml-benchmark/`: Claude Code plugin manifests
  validated with `claude plugin validate`. The citation instruction is
  transparent: the agent adds the citation and tells the user.
- **README** redesign: a banner, a workflow diagram, and every diagram
  rebuilt for dark mode (latex+dvisvgm).
- **Public-tree scrub**: VPS IPs, home paths, proxy details, and personal
  jurisdiction notes (moved to a gitignored local file). The old **git
  history still has them**, so it stays in the private archive (KI-47
  closed).
- Tests: 156 passed, 1 skipped (the real-framework E2E test, which needs
  installs).

**Next**: Ali turns on private vulnerability reporting and, optionally,
Zenodo (GitHub settings; see CLAUDE.md). The paper track resumes when Ali
says so, on the VPS Ali will provide (pilot sweep; the first real-framework
run of `prepare-data`, KI-15).

**Previous (2026-10-21): local abandoned, back to a VPS.** About an hour into
the local attempt below, FLAML had installed (32 min at about 2 MB/s
through Ali's proxy) but its smoke test hung on the first OpenML request.
openml.org was unreachable from the laptop's network: intercepted directly
(a 9 ms TCP connect, no TLS reply) and unanswered through the proxy. It
also failed from an outside vantage point, so OpenML may have been down too
(new KI-07). Ali: "forget about local as my network is trash. i'll provide
the vps". The run was stopped, and at Ali's request everything on the
drive, the old July venvs and `~/.cache/uv` were deleted. Ali removed
RocketChat (snap, purged) to free RAM. Kept: the local-drive scripts, the
`STORAGE_ENV_VARS` fix (a real bug, useful anywhere) and the
`caml doctor` fix. **Next**: Ali provides the VPS. Check that openml.org
answers from it, then provision, install, pilot, and run the AMLB audit.

**Earlier on 2026-10-21 (abandoned the same day): the pilot was to run on
Ali's laptop from an external drive.** Ali: "keep everything installed in there so i don't
have to pay a lot of money for vps". The laptop's system disk has about
13GB free, so everything goes under `/mnt/MIRC/CAML-STORAGE` (a 1TB USB HDD
with NTFS over ntfs-3g). The full runbook is
`docs/operations/local-storage.md`.
- Probed the drive first. Symlinks, hardlinks, sockets, FIFOs,
  flock/lockf, mmap and exec all work; it writes about 94 MB/s.
- New `scripts/sync_local.sh` deploys a REVISION-stamped copy and writes
  `caml-env.sh`. That file redirects HOME, the XDG dirs, the uv
  cache/Pythons and TMPDIR, with `UV_PYTHON_PREFERENCE=only-managed`.
  New `scripts/run_local_detached.sh` runs `setsid nohup systemd-inhibit`
  (sleep and lid-close blocked).
- **Found and fixed**: `run_in_venv` replaces the subprocess env, so a
  redirected HOME/XDG never reached 7 of the 10 frameworks. Their caches
  would have gone to the system disk. Fixed with the new `STORAGE_ENV_VARS`
  and `retained_env()` in `frameworks/shared/caller.py`, plus 2 tests.
- `caml doctor` now measures the workspace's disk, not `/`.
- uv had reused a system-disk interpreter; `only-managed` fixes that.
- Checked: system-disk free space was unchanged after deploying and
  building the orchestrator venv. Local suite: 121/121.
- **In progress**: a detached install and smoke test of the 10 pilot
  frameworks, with `CAML_COMPUTE=cpu`. The laptop has an RTX 3060 6GB, but
  the pilot stays CPU-only like AMLB. The log is at
  `/mnt/MIRC/CAML-STORAGE/logs/install-pilot.log`. Downloads run at about
  2 MB/s.
- New register entries: KI-14 (verify the redirect after real runs) and
  KI-33 (laptop as a benchmark box). Ali then approved the AMLB audit on
  the laptop's Docker and the deletion of the old July venvs plus
  `~/.cache/uv` (done, about 2GB freed). The system disk is an allowed
  fallback if something can't go on the drive. Committed as `35677e5` (not
  pushed).

**Paper track started (2026-10-20/21): sweep infrastructure built, pilot
ready, waiting on a new VPS.** Ali asked where a CAML paper could be
published, what arXiv requires, and what's left before a paper. Ali then
said "proceed with your plan" and set two rules: **all installs and runs on
a VPS, never locally**, and **documentation is the top priority**. The full
plan, venues and arXiv research are in `docs/research/paper-plan.md`. The
consolidated open-items register is the new
`docs/operations/known-issues.md`.

Done this session (local code and docs only; nothing installed or run
beyond unit tests):
- **`caml sweep`** (`src/caml/sweep.py`, `docs/operations/sweeps.md`): one
  isolated `caml run --task T --fold F --seed S --keep-going` subprocess per
  job. It has an append-only JSONL ledger (resume = re-run the same
  command) and per-job statuses (`ok/error/timeout/killed/crash/no_result`).
  It also hard-kills the job's process group on a timeout and reaps strays
  after every job, keeps an exclusive per-sweep lock, runs jobs
  fold-major, and supports `--shard K/N` and `--dry-run`/`--retry-failed`/
  `--max-jobs`.
- **Root-caused the documented "abort on first failure"**: `cli.py` hardcoded
  `exit_on_job_failure=True`, so a failed job also wrote **no row**, which
  silently biases `caml compare`. Added opt-in `caml run --keep-going`;
  the default is unchanged (decision KI-43).
- **`caml run --seed`**: `seed: auto` was random per process, so separate
  invocations weren't reproducible.
- **Provenance on VPS boxes**: `app_version` read `dev [NA, NA]` (no
  `.git`). `scripts/lib_package.sh` now stamps a `REVISION` file into every
  deploy, and `resources.git_info` falls back to it.
- **`scripts/sync_vps.sh`**: pushes code updates to an existing box (this
  replaces the manual scp workaround). It refuses while a job runs.
- **`pilot` benchmark + `pilot` constraint**: 9 AMLB-suite tasks (IDs read
  from the OpenML API), 2 folds × 600s × 4 cores, 180 jobs for 10 frameworks.
- **Claim-A experiment scripts** (`scripts/research/`): AMLB install audit,
  following AMLB's own documented install path in clean `ubuntu:22.04`/
  `24.04` containers.
- **Documentation gap closed**: the 2026-08-02 GPU SIGILL root cause (`HOME`
  missing from the subprocess env) and its fix (committed in `0be1a35`)
  were never written into the repo. Now documented in troubleshooting and
  `gpu.md`; still unverified (KI-10).
- Tests: `tests/test_sweep.py` adds 41 tests (local, no installs), all passing.

**Next** (revised later on 2026-10-21: no VPS, the laptop instead): finish
the installs and smoke tests on the drive. Then launch the pilot `caml
sweep` detached, which takes about 30–40h of laptop time and can run in
overnight chunks. Triage every failure, run the AMLB install audit
on the laptop's Docker (approved), and size the main sweep. *(Superseded plan: a rented 8 vCPU /
32GB VPS for about a week.)* Pending decisions: KI-40 to
KI-44 (license, TabPFN weights, TabPFNClient, keep-going default,
paper claim).

**Previous: statistical significance testing added, `caml compare` (2026-09-15).**
The user asked whether p-values could be added to compare frameworks; after
an explanation, they confirmed they want it built in, E2E-verified against
a bigger/more-realistic dataset than the 3-task toy smoke test, with docs
and scripts updated. Implemented per Demšar 2006 (the standard reference
for comparing learners across multiple datasets): paired **per task** (mean
`result` across folds — never per fold, to avoid pseudoreplication). New
`src/caml/stats.py` (pure pandas/numpy/scipy, no `caml.*`/`Scoreboard`
imports, directly unit-testable — same pattern as `feature_usage.py`) plus
a new `caml compare <fw1> <fw2> [<fw3>...] [--benchmark NAME] [--constraint
NAME] [--alpha FLOAT]` CLI command. 2 frameworks → Wilcoxon signed-rank +
paired t-test; 3+ → Friedman omnibus + a hand-rolled Holm-Bonferroni
pairwise post-hoc (chosen over the Nemenyi test specifically to avoid a new
`scikit-posthocs` dependency — more conservative, documented as a
trade-off). `scipy>=1.10` added as an explicit direct dependency (was only
an undeclared transitive dep of scikit-learn before). 26 new unit tests,
including several with hand-verified exact expected values (e.g. an 8-task
all-same-sign fixture asserting Wilcoxon's exact `p = 2×(1/2)⁸ ≈ 0.0078`,
not just `p < 0.05`), real scipy-1.18.0 zero-variance edge-case behavior
probed directly (it warns rather than raises — required a proactive
`np.allclose` pre-check, not a bare `try/except`), and a fixture proving a
degenerate/untestable pair is excluded from the Holm correction's family
size rather than silently deflating the pairs that DID compute. Local
suite: 80/80 (54 + 26 new).

**Verified on real data, local and VPS:**
- **Local**: `caml compare FLAML MLJARSupervised --benchmark test
  --constraint test` against this repo's own real, messy 76-row multi-session
  `output/results.csv` history (append-only, not deduplicated across
  sessions — a genuine, not synthetic, edge case) — real Wilcoxon/t-test
  p-values, the classification/regression metric-mix caveat fired correctly
  (test.yaml mixes both task types), no crash.
- **VPS** (10 vCPU/~2GB RAM; details in the gitignored
  `docs/operations/.vps-access.local.md`): ran FLAML and GAMA against the
  `validation` benchmark's real, bigger OpenML tasks (not the toy 3-task
  suite) under the `test` constraint. **This box is extremely RAM-tight**
  (confirmed: a single `bioresponse` job needs more RAM than the box has
  free) — the full unbounded 9-task sweep was abandoned in favor of
  targeted single-task runs (`--task <name>`) after two real operational
  lessons hit in this exact session: (1) an un-detached `ssh
  "long-command"` died when the driving connection dropped, exactly the
  failure mode already documented in
  `docs/operations/e2e-verification.md` — fixed by relaunching via
  `setsid nohup ... & disown`, written to a local script file and scp'd
  over rather than passed as a multi-line inline SSH string (inline
  multi-line SSH strings have repeatedly mangled in this project — always
  use a script file); (2) the dead and relaunched runs briefly overlapped,
  running two AutoML fits concurrently on a 2GB box — confirmed via `free
  -h` (used shot up to 1.7Gi/1.9Gi, SSH itself became flaky) before being
  caught and killed. **A real, non-CAML bug surfaced along the way**: GAMA
  on `bioresponse` (1776 columns) under the 60s `test` constraint hit
  `IndexError: list index out of range` in GAMA's own
  `postprocessing/best_fit.py` — its evolutionary search never evaluated a
  single individual in 60s on a dataset this wide, so its own
  post-processing selection step operated on an empty list. A real,
  believable framework-vs-budget mismatch, not a `caml compare`/`stats.py`
  bug — `caml run` aborts the whole multi-task invocation on a job's first
  fatal error (same behavior already documented for TPOT on
  `dresses-sales`), so recovering the OTHER tasks required one `--task`
  invocation per task rather than one multi-task run.
  **`caml compare FLAML GAMA --benchmark validation --constraint test`**
  against the resulting real data: correctly paired 3 shared tasks
  (eucalyptus, dresses-sales, internet-advertisements), correctly
  **excluded** `bioresponse` (`excluded_tasks: {bioresponse: [GAMA]}`,
  printed clearly under "Excluded tasks") since only FLAML had a row for
  it, real Wilcoxon p=1.0/t-test p=0.52 (not significant, small n=3 as
  expected), win/tie counts and the mixed-task-type t-test caveat all
  correct. This exercises both the "real comparison" and "graceful
  exclusion" paths against genuinely real data — considered sufficient
  proof without needing the full 9-task×4-framework sweep, which this
  particular box's RAM ceiling makes impractical.

Docs updated: `docs/reference/cli.md` (new `caml compare` section),
`README.md` (new subsection + command-reference row), `NOTICE.md` (new
"no AMLB precedent" entry — AMLB's own `amlb_report/` has descriptive
tables/plots only, no hypothesis testing), `docs/operations/
e2e-verification.md` (new closing section pointing at `caml compare`
as post-audit follow-up). `scripts/verify_e2e.sh` now echoes a
ready-to-copy `caml compare` suggestion for any benchmark with ≥2 PASS
frameworks, read only from data the script already collects (no new
failure modes). `docs/operations/.vps-access.local.md` updated with the
concurrent-run/RAM findings above.

---

**All three standing open items from 2026-09-10 closed out (2026-09-15).**
The user asked to proceed with all three: (1) extend TPOT/GAMA's
feature-usage extraction to catch the confirmed structural cases, (2) fix
the `run_subprocess` `StaleProcessError` race, (3) commit + push. Also
provided a new VPS (10 vCPU/**~2GB RAM**/29GB disk, details in the gitignored
`docs/operations/.vps-access.local.md`; the previous 2 vCPU box is superseded). RAM is the tightest this
project has worked with yet — below even the previous box's 3.8GB.

1. **TPOT/GAMA extraction extended**
   (`frameworks/shared/feature_usage.py::used_columns_from_pipeline()`):
   now tolerates identity-safe steps (`SimpleImputer`, literal
   `"passthrough"`) before a selector, and recognizes a selector nested
   inside a `FeatureUnion` when it's the union's only real branch (others
   `"drop"`/`None`). Still conservative — returns `None` for anything else
   (mixed-branch unions, more than one selector-capable point). 6 new unit
   tests against real fitted `sklearn.Pipeline`/`FeatureUnion` objects.
   **Confirmed live on the new VPS**: GAMA's iris fold-0 job reported
   `features_used=sepallength;petallength;petalwidth` (3 of 4 columns) —
   the first genuine subset this project has observed from any framework's
   feature-usage columns (previously always "all columns used" at this
   scale/budget). TPOT still didn't pick a selector on this run, so its
   `FeatureUnion` path is unit-tested but not yet observed live.
2. **`run_subprocess` race fixed**
   (`src/caml/utils/process.py::run_subprocess()`): a `process.poll()`
   reading `None` right after `communicate()` returns no longer means
   instant staleness — a short grace period (`process.wait(timeout=2)`)
   lets an already-exited-but-not-yet-reaped process resolve normally,
   while a genuinely stuck process still gets killed and reported after
   the grace window. 2 new regression tests
   (`tests/test_process.py`) using a real subprocess + a fake
   `communicate_fn` that reproduces the exact race shape. Re-verified
   across 4 fresh framework installs on the new VPS (TPOT/GAMA/
   LightAutoML/FLAML) — zero `StaleProcessError` occurrences.
3. **E2E re-verification**: all 4 frameworks (TPOT, GAMA, LightAutoML,
   FLAML) installed and run cleanly on the new VPS via
   `caml run <fw> --benchmark test --constraint test`, all 6 jobs each with
   real, plausible scores. Local suite: 54/54 (up from 45 — 9 new tests
   across the two fixes).
4. **Committed and pushed** — see the git log for the exact commit; this
   closes out the entire 2026-09-06→2026-09-15 feature-usage-reporting
   arc (design → report-only implementation → VPS verification → bug
   fixes → extraction extension → race fix → final re-verification).

---

**Feature-usage reporting verified on a real VPS, one real bug found and
fixed (2026-09-10).** The user provided a new box (plain CPU, 2 vCPU/3.8GB
RAM/116GB disk, details in the gitignored
`docs/operations/.vps-access.local.md`; not a GPU replacement, RAM is below
this project's own ≥8GB recommendation). Ran FLAML/TPOT/GAMA/LightAutoML
through `caml run <fw> --benchmark test --constraint test` and inspected
`output/results.csv`'s three new columns for real:

- **FLAML**: exactly as expected, `n_features_used == n_features_total` on
  all 6 jobs.
- **TPOT**: confirmed `tpot.fitted_pipeline_` really is an `sklearn.Pipeline`
  (direct diagnostic against a live fit). For these short 60s-budget fits it
  never actually picked a selector (steps came back as `Passthrough`/
  `FeatureUnion` wrappers around the final estimator), so "all columns used"
  was the *correct* report, not a bug. But this also surfaced a real,
  now-confirmed limitation: TPOT's linear template nests any real selector
  it does choose inside a `FeatureUnion`, which `used_columns_from_pipeline()`
  doesn't look inside — documented in `framework.toml`, not fixed (would be
  new scope).
- **GAMA**: same story — `gama_automl.model` confirmed to be a real (flatter
  than TPOT's) `sklearn.Pipeline`, no selector chosen in these fits, correct
  fallback. Confirmed limitation: GAMA's pipeline always imputes as step 0,
  so a real selector would land at step 1+ and never match the "selector
  must be first" check — documented, not fixed.
- **LightAutoML**: **found and fixed a real bug.** The original assumption
  (`leaf.used_features` as a plain attribute) was wrong — live introspection
  showed each leaf in `outer_pipes[*].ml_algos[*].models[*][*]` is actually a
  `TabularAutoML` wrapper instance exposing a real public method,
  `collect_used_feats() -> List[str]`. Fixed `union_of_branch_features()` to
  support calling a zero-arg method (not just reading an attribute), updated
  the call site, added 2 new tests (local suite now 45/45), re-verified
  end-to-end on the VPS post-fix — clean run, no introspection-failure
  warning. All three test datasets still came back "all columns used" at
  this small scale/short budget; a wider dataset would be a better test of
  whether it ever reports a genuine subset.

Also found along the way, not fixed (pre-existing, out of scope for this
task): a real, reproducible race in `caml.utils.process.run_subprocess`'s
activity-timeout watchdog (`StaleProcessError ... timed out after nan
seconds`) — hit 3 times against very fast one-line commands (`uv venv`,
`uv python install`) and once mid-job under CPU contention. Manual retries
always succeeded (the underlying command wasn't actually hung). Root cause
and repro notes in `docs/operations/.vps-access.local.md`; worth a real fix
if it keeps interrupting VPS work, flagged to the user rather than
unilaterally patched. Separately, this box is only 2 vCPU — running two
frameworks concurrently once corrupted GAMA's internal multiprocessing IPC
under contention; don't parallelize framework runs on this box.

---

**Local TabPFN added and verified (2026-07-31) — TabPFN now runs 100%
on-box.** The user asked whether TabPFN really needs the hosted API; the
answer was no. Built a new `TabPFN` framework around the OSS `tabpfn` package
(`tabpfn==8.1.0`, CPU torch wheel via `extra_index_urls`), and **renamed the
previous hosted entry `TabPFN` → `TabPFNClient`** (the user chose this naming:
local is the primary/default, the API client stays for GPU-less boxes). Key
finding: the local package was never a hard technical wall — the old "blocked
on a license gate" conclusion was correct *at the time* (no Prior Labs account
existed then) but went stale once the user created an account for the client
pivot. The only real blocker this pass was a one-time **TabPFN-3 license
acceptance** the user had to do in their Prior Labs account (the token was
already valid; `verify_token → True`, and the HF weight repo `Prior-Labs/
tabpfn_3` is ungated) — a genuinely user-only step, now done. After
acceptance, `caml run TabPFN --benchmark test --constraint test` passed 6/6
with real scores (kc2 AUC 0.855/0.910, iris acc 1.000/1.000, cholesterol RMSE
43.69/54.08), 1m52s incl. one-time weight download; `device="cpu"`, no
`exec.py` bugs. Full build log + auth-flow diagnosis in
`docs/frameworks/tabpfn.md`; the hosted variant is now
`docs/frameworks/tabpfn-client.md`. **License flag:** the TabPFN-3 *weights*
are non-commercial — fine for internal benchmarking on public data, but get a
legal read before any CAML result that used this framework leaves internal
use.

---

**E2E reliability verification experiment in progress (started
2026-07-31).** User request: wipe the VPS workspace entirely and
redeploy every framework *purely* from the committed, documented process
(no manual fixes, no relying on anything not written down), then test
every framework against both the `test` benchmark and a new `validation`
benchmark (9 real data-quality/type edge cases ported from AMLB —
missing values, stray whitespace in labels, boolean-like targets, a
non-last-column target, duplicate differently-cased category labels; see
`resources/benchmarks/validation.yaml`).

**Teardown + redeploy: clean success, purely from documented process.**
`scripts/teardown_workspace.sh` removed the entire 7.9GB workspace (repo,
AMLB reference clone, every framework venv, all run outputs) without
touching the `caml` OS user, `TABPFN_TOKEN`, or the apt baseline.
`scripts/provision_vps.sh` then rebuilt everything from a fresh
`git archive` of `HEAD` — `caml doctor` came back clean, and `caml
install --all` reproduced every framework at *exactly* the pin/Python
version already recorded in this file's Framework status table, with no
manual intervention. This is real, positive evidence the documentation
is self-sufficient, not just descriptive.

**Two real operational bugs found and fixed in the verification tooling
itself while running it** (both now fixed and pushed):
1. `scripts/verify_e2e.sh` was launched over a live `ssh ... "bash
   scripts/verify_e2e.sh"` pipe without detaching it on the remote side.
   When the harness session driving it ended, the dropped SSH connection
   SIGHUP'd the remote process mid-run — after 6 of 11 frameworks had
   already completed with real results (~12 hours of VPS compute, not
   lost — see below). Fixed: the script is now resumable (pass an
   existing results dir as `$1`; already-recorded framework/benchmark
   combos are read from its `summary.tsv` and skipped), and it must be
   launched with `setsid nohup ... & disown` (documented in the script's
   own header) so it survives the SSH connection closing.
2. The first resume attempt's skip logic silently didn't skip anything —
   `DONE["$fw\t$bench"]=1` (quoted subscript, preserves `\t` as a literal
   two-char escape) and `${DONE[$fw\t$bench]:-}` (unquoted subscript)
   build *different* keys, because bash's quote-removal strips the
   backslash from an unquoted `\t` but not a quoted one. Caught before it
   wasted the ~8 hours of already-captured validation results by
   re-running them — verified the fix against a real script file (not an
   inline shell command) before redeploying. Switched the key delimiter
   to `::` while fixing it, since that can't appear in a framework/
   benchmark name and avoids relying on getting subscript quoting exactly
   right on both sides at all.

**COMPLETE (2026-07-31) — full results in
`docs/operations/e2e-verification.md`.** All 11 frameworks x 2 benchmarks
ran. Headline: on **clean data** (`test`, 3 tasks) 10 of 11 pass (only
NaiveAutoML fails, on its known upstream bug); on **messy data**
(`validation`, 9 real data-quality edge cases) the roster splits — 7
frameworks clear all 9 tasks with zero crashes, 3 more choke on specific
messy-data tasks, NaiveAutoML fails everywhere. Exactly what the
experiment was for: the clean smoke test hid robustness differences that
only messy data exposes.

| Framework | `test` | `validation` | Failure cause |
|---|---|---|---|
| AutoGluon | PASS | PASS 9/9 | — |
| FLAML | PASS | PASS 9/9 | — |
| GAMA | PASS | PASS 9/9 | — |
| H2OAutoML | PASS | PASS 9/9 | — |
| LightAutoML | PASS | PASS 9/9 | — |
| MLJARSupervised | PASS | PASS 9/9 | — |
| TabPFNClient | PASS | PASS 9/9 | — |
| FEDOT | PASS | FAIL 7/9 | kc1 boolean-label round-trip + census-income OOM |
| SapientML | PASS | FAIL 7/8 | diabetes130US generated-pipeline `KeyError` (messy missing-values) |
| TPOT | PASS | FAIL 1/2 | dresses-sales "no individuals evaluated" (categorical+missing, tight budget) |
| NaiveAutoML | FAIL | FAIL 0/1 | confirmed-upstream `KeyError: nan` (already skipped) |

(The `TabPFNClient` row above is the hosted API — it's what ran during this
audit, under its then-name `TabPFN`. The local `TabPFN` framework was added
afterward, 2026-07-31, and passed the `test` benchmark. Its `validation` run
(2026-08-01) found **3/9 pass** — the other 6 fail on TabPFN-3's CPU
>1000-sample guard (a hardware limit, not a messy-data robustness gap: the
three ≤1000-row tasks pass). See `docs/frameworks/tabpfn.md`.)

None of the 3 validation failures is a CAML orchestrator bug — FEDOT's
kc1 is a plausibly-fixable label round-trip in its `exec.py` (flagged,
not fixed this pass), FEDOT's census-income is a box-size/OOM limit,
SapientML's is inside SapientML's *generated* pipeline code, TPOT's is
its own search failing on hard data within a short budget. Per-framework
detail appended to each of `docs/frameworks/{fedot,sapientml,tpot}.md`.

**Teardown + redeploy verified self-sufficient**: `teardown_workspace.sh`
→ `provision_vps.sh` rebuilt the entire workspace purely from committed
`HEAD` with zero manual steps, and `caml install --all` reproduced every
framework at exactly the recorded pin/Python. `caml doctor` green before
and after; no stray JVMs, 204GB disk free at the end.

**Two harness bugs found and fixed mid-audit** (both pushed, see
`troubleshooting.md`): an undetached remote SSH process that died on a
session boundary (now launched `setsid nohup ... & disown`, and
`verify_e2e.sh` is resumable), and a bash `\t`-array-key quoting mismatch
that would have re-run 8h of good results.

Full per-job logs are on the VPS under
`output/e2e_verify_20260730_214612/` (VPS-only run artifacts, not synced
to git). Standing follow-ups (none blocking, none started): a FEDOT
`exec.py` label-dtype fix for boolean targets; a longer-constraint
(`1h4c`) re-run to tell whether TPOT's dresses-sales failure is budget or
preprocessing; a decision on whether `caml run` should isolate-and-
continue past a hard task failure instead of aborting the batch (a design
call for the user, see the audit report).

**SapientML verified (2026-07-31, real VPS) — v1's 11-framework roster is
now fully built.** Not a numbered phase (v1/Phases 0-7 were already
closed out before this started) — the next active thread per the user's
decision to keep SapientML in the roster, now done. AMLB's four
"extending the benchmark" docs read and distilled first (the standing
gate), then a real correction made: this file and `CLAUDE.md` previously
said SapientML had no AMLB reference implementation to port from, which
was wrong (verified by reading the actual files — a real, if unpolished,
`exec.py` exists in both `openml/automlbenchmark` and the SapientML
team's own fork).

Install found and fixed three real upstream/environment issues: (1)
`tantivy==0.21.0` (locked in by `sapientml`'s own pin) has no cp313
wheel and its sdist fails to build under uv's stricter metadata checks
— `[python].range` capped at `<3.13`, same class of fix as LightAutoML/
FEDOT; (2) `nest_asyncio` is a genuine undeclared dependency (`sapientml`
imports it, neither `sapientml` nor `sapientml-core` lists it) — added
explicitly; (3) `sapientml-core`'s own `scipy<2.0,>=1.14.0` pin is too
loose — the default resolution (scipy 1.18.0) hits a scipy-internal
`TypeError` inside `kstest`, fixed with a `scipy==1.14.1` steering pin
(reproduced and confirmed in isolation, outside SapientML entirely).
`exec.py` itself needed one real fix after that: `predict_option` has to
be forced to `"default"`, since SapientML's own default silently changes
`predict()`'s output *shape* (not just its values) for any
probability-needing metric — auc/logloss both hit this on the first
smoke-test attempt.

After all four fixes: a clean 6/6 smoke test, real plausible scores in
line with every other verified framework — kc2 AUC 0.668/0.861, iris acc
0.933/1.000, cholesterol RMSE 46.57/54.42 — total wall-clock 85 seconds.
Full `pytest tests/` regression run afterward (unit + manifest-schema +
the full 8-framework `test_e2e_framework_run.py` E2E suite, now including
SapientML alongside AutoGluon/FEDOT/GAMA/H2OAutoML/LightAutoML/TPOT/
TabPFN) — **24 passed, 0 failed, 1178 warnings (all pre-existing), 37m55s.**
Zero regressions anywhere else in the roster from adding SapientML.

Full research writeup, live-verified current API, the CAML-metric-to-
`adaptation_metric` translation table, and the complete chronological
build log are all in `docs/frameworks/sapientml.md`, which is now the
primary reference for this framework going forward.

**Phase 7 (docs finalization) done (2026-07-30) — v1 is now
feature-complete and fully documented, modulo SapientML.** Read every doc
file in the repo looking for staleness against the completed Phase 0-6
work and fixed six real issues: a broken `mkdocs.yml` nav link
(`h2o-automl.md` → `h2o.md`), `docs/reference/cli.md` missing the `--task`
flag, `NOTICE.md`'s provenance ledger still listing 8 already-built
frameworks as "not yet built" (now has accurate entries across four
categories: ported-verbatim, ported-with-modification,
rewritten-entirely, no-AMLB-precedent), `docs/frameworks/naiveautoml.md`
still saying "blocked" instead of the user's actual "skip" decision, and
stale phrasing/no-status framework lists in `README.md`/`docs/index.md`.
Also added a Phase 6 entry to `docs/operations/troubleshooting.md`'s
durable-knowledge log. Deliberately left the four AMLB "extending the
benchmark" docs and anything SapientML-shaped untouched — both still
explicitly deferred. See `CLAUDE.md`'s Phase 7 writeup for the full list.

No phase is now in progress — see the Phase checklist below and
`CLAUDE.md`'s "Immediate next step" for the standing open items
(SapientML's eventual revisit, the open invitation to suggest further
frameworks, Phase 8 backlog).

**Phase 6 (cross-cutting hardening) verified (2026-07-30) — all three
known candidate items closed, Phase 6 is now done.**

1. **AutoGluon CPU-only torch wheel fix.** Added
   `extra_index_urls = ["https://download.pytorch.org/whl/cpu"]` to
   `frameworks/AutoGluon/framework.toml` (same fix already proven for
   LightAutoML). `caml uninstall AutoGluon && caml install AutoGluon` on
   the real VPS resolved `torch==2.9.1+cpu` (`torch.version.cuda is
   None`), pulling zero `nvidia-*` packages — venv totals 2.7GB (the full
   `tabular[all]` stack, not just torch). Re-ran the smoke test
   afterward: all 6 jobs produced scores identical to the original
   verification (kc2 AUC 0.853/0.932, iris acc 0.933/1.000, cholesterol
   RMSE 44.16/54.65) — confirms the wheel swap changed nothing
   behaviorally. See `docs/frameworks/autogluon.md`.
2. **`openml-python` client-side timeout gap**, flagged in this file's
   Notes since the OpenML outage earlier in the project (one call sat
   silent ~53 minutes before a 504). Fixed in
   `src/caml/benchmarks/openml.py` by patching `requests.Session.request`
   to apply a 120s default timeout whenever a caller doesn't specify one
   — orchestrator-only module, never imported inside a framework's
   isolated subprocess venv, so this can't break a framework venv lacking
   `requests`. Worth flagging: `socket.setdefaulttimeout()` does **not**
   fix this (empirically confirmed — `requests`/`urllib3` ignore the
   socket-level default when no explicit `timeout=` is passed), so the
   patch has to sit at the `requests.Session` layer itself. Covered by a
   new real regression test, `tests/test_openml_http_timeout.py`, using
   an actual hung TCP listener (not a mock) — checks both that an
   unspecified timeout now fails fast and that a caller-supplied timeout
   still wins over the installed default.
3. **CLI task/fold-scoping flag.** Already implemented at the Phase 5→6
   boundary (`--task`, commit `e2213bf`; `--fold` pre-existed) — this
   entry just confirms it's fully resolved, not still an open item.

All three re-verified together: a fresh `git archive` sync to the VPS,
then `pytest tests/` (unit + manifest-schema + the new HTTP-timeout test
+ the full 7-framework `test_e2e_framework_run.py` E2E suite) — **22
passed, 0 failed, 975 warnings (all pre-existing deprecation/pandas
noise, none new), 37m22s.** Zero regressions from any Phase 6 change.

**Phase 5 is done** (see below); **Phase 6 is now done too**. Next up:
Phase 7 (docs finalization).

**GAMA verified (2026-07-30) — Phase 5's fourth and final framework this
pass, closing out Phase 5.** The health-flagged, time-boxed framework in
the roster (last PyPI release 2024-06-14, last GitHub push 2024-09-04,
both re-confirmed live before starting) — came up clean well within the
timebox, no need to escalate to the user for a best-effort downgrade call.
Also found a real discrepancy in GAMA's own metadata worth knowing about:
its `pyproject.toml` declares `license = {text = "MIT"}`, but the actual
`LICENSE` file at the repo root is Apache License 2.0 (confirmed both via
GitHub's own license detection and reading the file directly) — treated
the actual `LICENSE` file as authoritative, matching this project's
existing Apache-2.0 classification.

Two real install bugs found and fixed, zero `exec.py` bugs:
1. `numpy<2` steering pin — GAMA's own `scikit-learn<1.3` pin resolves to
   `scikit-learn==1.2.2`, which predates numpy 2.0 and whose compiled
   extensions (`sklearn.utils.murmurhash`) crash on import
   (`ValueError: numpy.dtype size changed...`) against a numpy 2.x
   runtime — same class of fix as H2OAutoML's identical pin, third
   framework in the roster needing it.
2. `setuptools<82` steering pin — surfaced one import deeper once fix #1
   cleared: GAMA's `stopit` sub-dependency (the *same* `stopit` package
   that caused TPOT's original instance of this bug) does a bare
   `import pkg_resources`, which fails on a bare `uv venv` + current
   setuptools. Third framework in the roster needing this exact pin.

After both fixes: install and the full 6-job smoke test went cleanly.
Scores: kc2 AUC 0.890/0.887 (acc 0.811/0.792, balacc 0.646/0.500), iris
acc 0.933/1.000, cholesterol RMSE 42.14/53.96 — all in line with every
other verified framework. `caml doctor` clean afterward. One non-blocking
observation: `models_count` reports exactly `50` on every single job
(GAMA's `_final_pop` appears to reflect total individuals evaluated
across the whole EA run, not the final generation's population) — not
investigated further. Full detail in `docs/frameworks/gama.md`.

**Phase 5 is now done.** NaiveAutoML skipped (confirmed-upstream bug),
LightAutoML/FEDOT/GAMA all verified. SapientML remains deferred to a
future pass per the user's explicit decision — not a blocker for closing
this phase. Next up: Phase 6 (cross-cutting hardening).

**FEDOT verified (2026-07-30) — Phase 5's third framework, second to land
clean with only an install-level fix.** Pin/API verified live against
`github.com/aimclub/FEDOT` (tag `v0.7.5`) before writing any code: despite
FEDOT being far more actively developed than TPOT/NaiveAutoML (both of
which had real breaking drift from AMLB's reference), the `Fedot` class
API AMLB's `exec.py` uses was completely unchanged — including a
non-obvious bit worth having actually checked rather than assumed:
`metric`, `max_pipeline_fit_time`, and `preset` aren't named constructor
parameters at all (they flow through `**composer_tuner_params` into
`ApiParams`), and `ApiParamsRepository.check_and_set_default_params()`
raises a hard `KeyError` for anything not in its own allowlist — all three
are still allowlisted. `.fit()`/`.predict()`/`.predict_proba()` signatures
and `.current_pipeline.length` (inherited from GOLEM's `GraphDelegate`)
all confirmed unchanged too. `exec.py` is therefore a near-verbatim port.

One real install bug found and fixed, the same class as TPOT's: importing
`fedot` itself raised `ModuleNotFoundError: No module named
'pkg_resources'` (`fedot → golem.core.tuning.simultaneous → hyperopt`,
whose `atpe.py` does a bare `import pkg_resources`) — a bare `uv venv`
doesn't bundle `setuptools`, and `setuptools>=82.0.0` dropped
`pkg_resources` entirely even when present. Fixed with the identical
`setuptools<82` steering pin TPOT already needed — FEDOT is the second
framework in the roster to hit this, worth checking for first if a future
framework's install fails the same way. Also confirmed empirically (not
just researched): `fedot`'s own `scipy<1.13.0` pin has no cp313 wheel
(newest match is scipy 1.12.0, cp39–cp312 only), so `[python].range` is
capped at `<3.13`, same class of fix as LightAutoML's `statsmodels` pin.

After both fixes: install and the full 6-job smoke test went cleanly,
zero `exec.py` bugs. Scores: kc2 AUC 0.846/0.873 (acc 0.811/0.868, balacc
0.613/0.749), iris acc 0.933/1.000, cholesterol RMSE 42.57/53.67 — all in
line with every other verified framework. `caml doctor` clean afterward.
Full detail in `docs/frameworks/fedot.md`.

**LightAutoML verified (2026-07-30) — Phase 5's second attempted
framework, first to actually land.** Pin/API verified live against
`github.com/sb-ai-lab/LightAutoML` — unlike TPOT/NaiveAutoML, no breaking
API drift from AMLB's reference at all (`TabularUtilizedAutoML`'s
constructor, `Task`'s valid name strings, and the
`reader.class_mapping` attribute the label-recovery code needs are all
unchanged), so it ported closely.

One real install bug found and fixed: `lightautoml`'s own classifiers
claim Python 3.8–3.13, but its `statsmodels<=0.14.0` dependency pin has
no prebuilt wheel for 3.13 (confirmed live via PyPI's file listing —
wheels exist for cp38–cp312 only), so the first install attempt fell back
to a source build that failed outright (`Cython.Compiler.Errors.CompileError`
in `statsmodels/nonparametric/linbin.pyx`). Fixed by capping
`[python].range` at `<3.13`, forcing resolution to 3.12. Also deliberately
skipped AMLB's `setup.sh`'s unconditional `apt-get install python3-opencv`
(not needed — `opencv-python` is an optional CV-extras group `lightautoml`
never pulls by default, and CAML's `exec.py` only touches tabular
presets); confirmed on the real VPS that this was safe to drop.

After the Python-version fix: install and the full 6-job smoke test both
went cleanly, zero `exec.py` bugs. Scores: kc2 AUC 0.870/0.884, iris acc
1.000/1.000, cholesterol RMSE 42.50/54.54 — all in line with every other
verified framework. One non-blocking observation: kc2's `acc`/`balacc`
looked low relative to its AUC (balanced accuracy exactly 0.5 on both
folds) — most likely explained by `Task()` not being wired to CAML's
actual scoring metric (matches AMLB's own original integration) combined
with naive argmax-thresholding on kc2's real class imbalance, not a code
bug — see `docs/frameworks/lightautoml.md` for full detail.

`tests/test_e2e_framework_run.py` run twice against all 5 now-installed
frameworks together (AutoGluon, TPOT, H2OAutoML, TabPFN, LightAutoML): the
first run had TPOT hit the test benchmark's actual 120s hard subprocess
timeout on `iris.1` (the "test" benchmark's real per-task budget is 60s —
`resources/benchmarks/test.yaml`'s `__defaults__`, not the 600s in
`constraints.yaml`, which is a looser ceiling — giving
`job_timeout_seconds = min(60*2, 60+3600) = 120`). TPOT's own
genetic-programming search has real run-to-run variance in which
pipelines it evaluates; an immediate retry passed cleanly (5/5), so this
reads as a one-off slow draw, not a regression — TPOT hasn't been touched
since its own verification. Worth knowing the actual 60s/120s numbers if
a similar flake shows up again.

**NaiveAutoML (Phase 5, first Tier-2 framework attempted) — one real bug fixed, one
confirmed-upstream bug blocking every task; user decided to skip it
(2026-07-30), same as SapientML.**
Drafted against the current `naiveautoml` API (real API drift found vs.
AMLB's reference: `timeout=`/`execution_timeout=` don't exist anymore,
current kwargs are `timeout_overall`/`timeout_candidate`). Install went
cleanly (all hard pins — `numpy<2`, `scikit-learn==1.5.2`,
`configspace==1.2.0`, `scikit-multilearn==0.2.0` — resolved fine despite
`scikit-multilearn` not having shipped a release since December 2018).

Smoke test surfaced two bugs:
1. **Fixed**: AMLB's `max_hpo_iterations=1e10` is a Python float; current
   `naiveautoml` does `range(self.task.max_hpo_iterations)` internally,
   which needs an int. Independently corroborated —
   github.com/fmohr/naiveautoml issue #75 reports another user hitting
   this exact error running NaiveAutoML under AMLB with short time
   constraints.
2. **Not fixed, confirmed upstream**: after the float fix, every task in
   the test benchmark (kc2, iris, cholesterol — not dataset-specific)
   still fails with `KeyError: nan` inside `naiveautoml`'s own `fit()`.
   Root cause, traced via a scoped single-task diagnostic script (same
   pattern used for TPOT's bug earlier): `naiveautoml.py`'s
   `as_result_for_best_candidate` is built from the single
   globally-highest-scoring row across the *entire* per-phase evaluation
   history, not from a row that actually corresponds to the final decided
   combination of pipeline steps. When that best-scoring row comes from
   an early, single-step evaluation phase, other steps' `_class` columns
   are NaN in that row, and a later lookup (`get_config_space_for_selected_algorithms`)
   crashes trying to use NaN as a dict key. Reproduced consistently across
   independent runs; the GitHub issue above shows this general class of
   problem (AMLB-style integration + short time budgets) is known, not
   specific to CAML's port. This is inside `naiveautoml`'s own package
   code — patching it would mean forking/monkeypatching a third-party
   dependency, a bigger intervention than any other framework in this
   roster has needed.

User's call (2026-07-30): skip it and move to LightAutoML, same treatment
as SapientML — not load-bearing for the project. Full diagnosis kept in
`frameworks/NaiveAutoML/framework.toml`'s gotchas and
`docs/frameworks/naiveautoml.md` in case anyone revisits it later (e.g. if
`naiveautoml` ever ships a fix upstream).

**SapientML build-out started 2026-07-31.** Un-skipped in a prior session
(the user wants it added, just not immediately); now the active work
thread. AMLB's four official "extending the benchmark" docs (see the
former "Extending the benchmark" note below, now resolved) have been read
and distilled into `docs/frameworks/sapientml.md` Part 1. **A real
correction to earlier notes in this file and `CLAUDE.md`**: both claimed
SapientML has no AMLB reference implementation to port from — false,
confirmed by actually reading the files. `automlbenchmark-reference/frameworks/SapientML/exec.py`
is a real (if unpolished) ~90-line implementation, and the SapientML team
maintains their own AMLB fork with a near-identical copy (one bug: a
stray `=` where `==` was meant). Full live-verified API research
(`SapientML`/`SapientMLConfig`, metric translation table, reasoned
deviations from both AMLB references) is in `docs/frameworks/sapientml.md`
Part 2. Status: `in-progress`.

**H2O AutoML verified (2026-07-30) — Phase 4 is done, first-try clean
install and run.** The first framework in the roster with a runtime
dependency outside Python itself (a JVM child process via `h2o.init()`),
and the first needing an apt system package (`openjdk-17-jre-headless`).
Both the apt-install path (`installer.py`'s `_ensure_apt_packages()` +
the `caml` user's NOPASSWD sudoers entry) and `caml doctor`'s
`pgrep -f h2o.jar` stray-JVM check were built speculatively back in Phase
0 — both worked correctly the first time they were actually exercised.

Two real, documented-but-not-widely-known H2O-3 constraints went into
`framework.toml` after verifying live against `docs.h2o.ai`: the Python
client only supports up to 3.11 (no 3.12/3.13, unlike every other Tier-1
framework so far — PyPI's own `requires_python` metadata doesn't
communicate this), and H2O-3 requires `numpy<2` (added as a steering pin,
same class of fix as MLJARSupervised's `numba>=0.60` and TPOT's
`setuptools<82`). With those in place, install and the full 6-job smoke
test (kc2/iris/cholesterol × 2 folds) both went cleanly on the first
attempt — no bugs found, a first for this roster. Scores: kc2 AUC
0.866/0.873, iris acc 1.000/1.000, cholesterol RMSE 45.47/54.72, all in
line with every other verified framework. `caml doctor` confirmed no
orphaned JVMs after the run, and `tests/test_e2e_framework_run.py` passed
for all three installed frameworks together (AutoGluon, H2OAutoML, TPOT —
3 passed in 1108s). Full detail in `docs/frameworks/h2o.md`.

**TPOT verified (2026-07-30) — Phase 3's second framework is done, three
real bugs found and fixed along the way.** Drafted from scratch against
TPOT's current (post-2025-rewrite) API rather than porting AMLB's
pre-rewrite reference (see `docs/frameworks/tpot.md` for the full API-diff
writeup: `config_dict=`→`search_space=`, `scoring=`→`scorers=`/
`scorers_weights=`, `evaluated_individuals_`→`evaluated_individuals`).

Bringing it up on the VPS surfaced three real, fixed bugs — a good example
of why this project insists on actually running things rather than trusting
research alone:
1. **General installer bug**: `src/caml/frameworks/installer.py` joined
   package specs into a shell command with no escaping. Every framework
   until now used an exact `==` pin (no shell meaning); TPOT was the first
   needing a comparison operator (`setuptools<82`), which `/bin/sh`
   misparsed as I/O redirection. Fixed with `shlex.quote()` — see
   `docs/operations/troubleshooting.md`. Would have hit any future
   framework needing a non-`==` pin (e.g. NaiveAutoML's planned `numpy<2`).
2. **`setuptools<82` steering pin** (TPOT-specific, same class of fix as
   MLJARSupervised's `numba>=0.60`): `tpot`'s `stopit` sub-dependency does
   a bare `import pkg_resources`, which fails on a bare `uv venv` combined
   with current setuptools (removed `pkg_resources` entirely as of 82.0.0).
3. **`tpot.classes_` mapping fix** (TPOT-specific): `TPOTClassifier.predict()`
   returns its own internal integer-encoded classes, not the original
   labels — unlike every other framework's underlying library. Caused a
   100%-reproducible `ResultError` on every classification job until
   `exec.py` started mapping predictions through `tpot.classes_`.

Once fixed: all 6 jobs (kc2/iris/cholesterol × 2 folds) produced real,
plausible scores in line with every other verified framework (kc2 AUC
0.864/0.934, iris acc 1.000/1.000, cholesterol RMSE 44.15/54.29), and
`tests/test_e2e_framework_run.py` passed too.

**AutoGluon verified (2026-07-29) — Phase 3's first framework is done.**
The Phase-2 VPS was deleted; a replacement was provisioned 2026-07-26 (same
specs: 4 vCPU/7.8GB RAM/232GB disk, new IP — see
`docs/operations/.vps-access.local.md`) via `scripts/provision_vps.sh`,
which went green first try. AutoGluon's manifest/`exec.py` (drafted
2026-07-21, committed 2026-07-26 in `57a94b3`) installed cleanly — full dep
tree (torch, catboost, lightgbm, xgboost, ray, etc.), zero install errors.

The smoke test was blocked for about 3 days (2026-07-26 ~11:55 through
2026-07-29 ~11:30) on an OpenML API outage — their `/api/v1/xml/task/*`
endpoint stopped responding entirely (confirmed external, not ours; see the
"OpenML outage, resolved" note below). Once OpenML recovered, `caml run
AutoGluon --benchmark test --constraint test` completed cleanly: all 6 jobs
(kc2/iris/cholesterol × 2 folds) produced real, plausible scores in line
with FLAML/MLJAR (kc2 AUC 0.853/0.932, iris acc 0.933/1.000, cholesterol
RMSE 44.16/54.65). Also confirmed via `tests/test_e2e_framework_run.py` —
passed. One real (but non-blocking) bug surfaced: AutoGluon 1.5.0's own
`fastai`/`fastcore` pin combination breaks its NeuralNetFastAI model
(`AttributeError` on every job) — AutoGluon's own exception handling routes
around it automatically, so scores are unaffected. Full detail in
`docs/frameworks/autogluon.md`'s gotchas — this is an upstream bug, not a
CAML one, not fixed here.

**TabPFN verified (2026-07-30) — pivoted from the local `tabpfn` package
to Prior Labs' hosted `tabpfn-client` and confirmed working end-to-end.**
*(Update 2026-07-31: this hosted entry was later renamed `TabPFNClient`, and
a local `TabPFN` framework added — see the top "Currently working on" entry.
The `frameworks/TabPFN/…` and `docs/frameworks/tabpfn.md` paths named below
describe the pre-rename layout; the hosted variant now lives at
`frameworks/TabPFNClient/` and `docs/frameworks/tabpfn-client.md`.)*
The original `tabpfn==8.1.0` local-package attempt (2026-07-29) got
blocked on a one-time Prior Labs account + license gate before it would
serve model weights (full history preserved below and in git history).
Rather than wait further, the user registered a Prior Labs account,
accepted the license, and created an API key, then asked to switch to
`tabpfn-client` (Prior Labs' hosted-API client) instead — this sidesteps
the local weight-download gate entirely, at the cost of a real
architectural change: `tabpfn-client` sends training/test data to Prior
Labs' servers for processing over HTTPS, unlike every other framework
here, which runs 100% locally (see `CLAUDE.md`'s license-flags section and
`frameworks/TabPFN/framework.toml`'s gotchas for the full implication).
`packages` is now `tabpfn-client==0.3.3`, no torch/`extra_index_urls`/
`post_install_script` needed anymore (nothing to pre-warm — all compute is
server-side). Auth is via a `TABPFN_TOKEN` environment variable
(`docs/operations/tabpfn-access.md`); `exec.py` fails fast with a clear
error if it's unset.

Install and the full 6-job smoke test both went cleanly on the first
attempt after the pivot — zero exec.py bugs. Scores: kc2 AUC 0.859/0.910,
iris acc 1.000/1.000, cholesterol RMSE 43.42/54.07, all in line with every
other verified framework. Full detail in `docs/frameworks/tabpfn.md`.

**Credential-handling note for future sessions**: partway through this
pass, the user's real TabPFN API key ended up pasted into the *committed*
`docs/operations/tabpfn-access.md` (no `.local` in the name) instead of
the gitignored `docs/operations/.tabpfn-access.local.md` created for that
purpose — an easy mix-up given the similar filenames. Caught before
anything was staged or pushed; the tracked file was reverted to its
placeholder and the real key moved to the correct gitignored file plus
the VPS `caml` user's environment. Worth double-checking which of the two
files you're editing if this comes up again.

Also landed in this pass:
- `tests/test_e2e_framework_run.py` — a real pytest test (not just a manual
  runbook step) that runs every *installed* framework against the test
  benchmark and asserts non-NaN scores. Already validated locally against
  FLAML/MLJAR (both still have local venvs from Phase 1) — all green.
- A real bug fix in `src/caml/datasets/openml.py`: openml-python >=0.15 no
  longer populates `_oml_dataset.data_file`; added a
  `_oml_cached_file_base()` fallback. Needed for AutoGluon's parquet-path
  data loading (FLAML/MLJAR's array-based splitters never hit this).
- **New policy: no more local framework installs, ever** (disk-space
  constrained local machine). `caml install`/`caml run` now only happen on
  the VPS. See `CLAUDE.md`'s "Local vs. VPS work" section.

Phase 2 (2026-07-21) verified FLAML + MLJAR-supervised end-to-end on a real
VPS with zero new code bugs, and added the one-shot `provision_vps.sh`
(see commit `6b68fbc` for full detail). Phase 1 (2026-07-18, dev sandbox)
found and fixed six real bugs — see `docs/operations/troubleshooting.md`
and `NOTICE.md`.

## Phase checklist

- [x] Phase 0 — repo bootstrap (GitHub repo, AMLB reference clone, tree scaffold, licenses, CLAUDE.md/STATUS.md)
- [x] Phase 1 — plugin contract + FLAML + MLJAR-supervised reference implementations (local) — both verified end-to-end, 2026-07-18
- [x] Phase 2 — VPS handoff + bootstrap — provisioned real Ubuntu 24.04 box, FLAML + MLJAR re-verified E2E, one-shot `provision_vps.sh` added & tested, 2026-07-21
- [x] Phase 3 — Tier 1 rollout: AutoGluon (done, 2026-07-29), TPOT (done, 2026-07-30), TabPFN (done, 2026-07-30, pivoted to tabpfn-client) (VPS)
- [x] Phase 4 — H2O AutoML (JVM) (VPS) — done, 2026-07-30, first-try clean
- [x] Phase 5 — Tier 2 rollout: NaiveAutoML skipped (confirmed-upstream bug, 2026-07-30), LightAutoML (done, 2026-07-30), FEDOT (done, 2026-07-30), GAMA (done, 2026-07-30) — SapientML deferred to a future pass, not dropped (see Framework status)
- [x] Phase 6 — cross-cutting hardening (VPS): AutoGluon CPU-only torch wheel fix, openml-python client-side timeout, `--task` CLI flag confirmed resolved — done, 2026-07-30
- [x] Phase 7 — docs finalization: fixed 6 real staleness issues across mkdocs.yml/NOTICE.md/README.md/docs/ — done, 2026-07-30
- [ ] Phase 8 — backlog (not v1): version-check bot, GPU auto-detection (default to GPU when available, fall back to CPU otherwise — not forcing GPU support onto frameworks that don't have it; see `CLAUDE.md`'s "Compute target" section), more frameworks, report/upload parity

## Framework status

Status ∈ `not-started | in-progress | blocked | skipped | verified`.

| Framework | Tier | Status | Pinned Version | Python | Last Verified | Issue |
|---|---|---|---|---|---|---|
| FLAML | 1 | verified | 2.6.0 | 3.12 | 2026-07-21 (real VPS) | — |
| MLJARSupervised | 1 | verified | 1.3.1 | 3.12 | 2026-07-21 (real VPS) | — |
| AutoGluon | 1 | verified | 1.5.0 | 3.12 | 2026-07-30 (real VPS, CPU-torch-wheel re-verify) | — |
| TabPFN | 1 | verified | tabpfn 8.1.0 | 3.12 | 2026-07-31 (real VPS) | **local OSS package, runs on-box**; needs 1-time Prior Labs license acceptance for weight download; weights are non-commercial — see `docs/frameworks/tabpfn.md` |
| TabPFNClient | 1 | verified | tabpfn-client 0.3.3 | 3.13 | 2026-07-31 (real VPS, post-rename reinstall) | hosted API — **data leaves the box**; GPU-less fallback; was the original `TabPFN` — see `docs/frameworks/tabpfn-client.md` |
| TPOT | 1 | verified | 1.1.0 | 3.13 | 2026-07-30 (real VPS) | — |
| H2OAutoML | 1 | verified | 3.46.0.11 | 3.11 | 2026-07-30 (real VPS) | — |
| LightAutoML | 2 | verified | 0.4.2 | 3.12 | 2026-07-30 (real VPS) | — |
| SapientML | 2 | verified | 0.4.17 | 3.12 | 2026-07-31 (real VPS) | steering pins needed: `scipy==1.14.1`, `nest_asyncio==1.6.0` — see `docs/frameworks/sapientml.md` |
| FEDOT | 2 | verified | 0.7.5 | 3.12 | 2026-07-30 (real VPS) | — |
| NaiveAutoML | 2 | skipped | 0.1.6 | 3.12 | — | confirmed-upstream KeyError, user decided to skip, 2026-07-30 |
| GAMA | 2 | verified | 23.0.0.post1 | 3.11 | 2026-07-30 (real VPS) | — |

## Notes

- **Extending the benchmark: official AMLB docs — read and distilled
  2026-07-31.** Done — see `docs/frameworks/sapientml.md` Part 1 for the
  full distillation (what CAML already replaced vs. what's still
  load-bearing in `exec.py`'s contract). The four pages read:
  <https://openml.github.io/automlbenchmark/docs/extending/>,
  <https://openml.github.io/automlbenchmark/docs/extending/benchmark/>,
  <https://openml.github.io/automlbenchmark/docs/extending/constraint/>,
  <https://openml.github.io/automlbenchmark/docs/extending/framework/>.
  This was the standing gate before SapientML's build-out (or any
  framework beyond the original 11) could start — now resolved. The user
  is still open to suggesting further frameworks beyond v1, with an
  explicit ask to stay consistent with how frameworks are added here.

- **VPS was recreated 2026-07-26** (the Phase-2 box was deleted). Same
  specs (4 vCPU/7.8GB RAM/232GB disk), new IP — see
  `docs/operations/.vps-access.local.md`. Re-provisioned clean via
  `scripts/provision_vps.sh root@<host>` (SSH key-based auth; that script
  doesn't support password auth, so if a future box only offers a
  password, bootstrap a key first — see the note in the access file).
- **OpenML outage, resolved.** Their `/api/v1/xml/task/*` API was
  completely unresponsive from 2026-07-26 ~11:55 to some point before
  2026-07-29 ~11:30 (confirmed recovered then, HTTP 200 in ~1s) — about 3
  days. Confirmed external at the time (DNS/TCP/TLS fine, their app layer
  just didn't answer; their own status page was too stale to be useful).
  No code change was needed; it simply came back. Kept for the historical
  record in case a similar hang recurs — if so, this isn't new, just
  check `curl --max-time 10 <task-api-url>` before assuming it's us.
- **Apt-package install path validated end-to-end (2026-07-30).** H2O was
  the first framework needing a `system_packages.apt` entry
  (`openjdk-17-jre-headless`); `installer.py`'s `_ensure_apt_packages()`
  (via `sudo -n apt-get install`) and the `caml` user's NOPASSWD sudoers
  entry from `scripts/bootstrap_vps.sh` had been sitting untested since
  Phase 0 and both worked on the first real attempt. Any future framework
  needing an apt package should now be low-risk on this front.
- **`openml-python`'s missing client-side timeout — resolved 2026-07-30
  (Phase 6).** During the outage above, one attempt sat silent for ~53
  minutes before OpenML's own gateway returned a `504`, instead of
  failing fast. Fixed via `src/caml/benchmarks/openml.py::install_default_http_timeout()`
  (patches `requests.Session.request` with a 120s default whenever a
  caller doesn't specify one — `socket.setdefaulttimeout()` does **not**
  work for this, confirmed empirically, see `CLAUDE.md`'s Phase 6
  writeup). Covered by `tests/test_openml_http_timeout.py`.
- Minor, non-blocking observations from the VPS run (not bugs):
  - FLAML/MLJAR pull `nvidia-nccl-cu12` (~289MB) transitively via
    xgboost's Linux wheel — unused on a CPU box, just disk/bandwidth. Left
    as-is; revisit if disk pressure appears or in the Phase-8 GPU work.
  - The per-fold "Metric scores" debug dict logs `duration: nan`; the
    aggregated `output/results.csv` has the real per-job durations. Cosmetic
    (job-level duration is attached after that log line), not a data bug.
- See `CLAUDE.md` for architecture decisions and research findings behind every choice here.
