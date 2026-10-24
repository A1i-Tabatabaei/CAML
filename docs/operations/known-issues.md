# Known issues and open items: the register

**One list of everything that is still open**: bugs not yet fixed, fixes
not yet verified, upstream limitations, and decisions that need Ali. Each
entry points to the page with the full write-up (symptom, root cause,
evidence). When something is fixed *and verified*, move it to "Recently
closed" with the date and commit. Don't delete it: the history is part
of the record (and of the paper's failure analysis).

Created 2026-10-21 by consolidating items scattered across `STATUS.md`,
`CLAUDE.md`, `operations/troubleshooting.md`, `operations/e2e-verification.md`
and the framework pages. Last updated: 2026-10-24 (v1.1.0: Windows, macOS and Linux operators, camlctl).

Status legend: **open** (not fixed) · **fixed, unverified** (code changed,
not yet proven on a real box) · **upstream** (a framework's own bug,
documented, not fixable from CAML without patching that framework) ·
**limit** (a hardware/budget limit, not a bug) · **decision** (needs Ali).

## CAML-side: actionable

| ID | Issue | Status | Details | Next action |
|---|---|---|---|---|
| KI-01 | `caml sweep` and `caml run --keep-going` have never run against real AutoML frameworks. The sweep bookkeeping is unit-tested with a fake runner. **2026-10-24**: `--keep-going` → error row is now proven end to end with a deliberately failing stand-in framework (`tests/test_file_dataset_pipeline.py`), which found and fixed a crash that would have lost every error row (troubleshooting, 2026-10-24). | fixed, partly verified | `operations/sweeps.md`, troubleshooting 2026-10-21 and 2026-10-24 | First pilot sweep on the VPS: confirm a real framework exception becomes an `error` row and ledger record. |
| KI-02 | No merge step for sharded multi-box sweeps (each box has its own `results.csv` and ledger). | open | `operations/sweeps.md` | Build before the multi-box main sweep (not needed for the single-box pilot). |
| KI-03 | `results.csv` has no `benchmark` column. Same-named tasks from different benchmarks (`kc1` = task 3917 in `validation`, 359962 in `pilot`) are separable only by `id` or by constraint, and `caml compare` groups by task *name*. | open | `resources/benchmarks/pilot.yaml` header, `operations/sweeps.md` | Mitigated by the distinct `pilot` constraint. Consider adding a `benchmark` column (touches the AMLB-ported `Scoreboard` schema). |
| KI-04 | Peak memory per job isn't recorded; an OOM shows up only as `killed` plus `dmesg`. | open | `operations/sweeps.md` | Add per-job peak RSS to the ledger if the pilot shows memory is the deciding factor. |
| KI-05 | FEDOT on `kc1` (true/false labels): `ResultError: y contains previously unseen labels: np.str_('0.0')`, the pandas bool round-trip trap. Plausibly fixable in `frameworks/FEDOT/exec.py` by enforcing string dtype. | open | `frameworks/fedot.md`, `operations/e2e-verification.md` | Fix in `exec.py`, then verify on `pilot`'s `kc1`. |
| KI-07 | OpenML's API is a single point of failure for every run: datasets and task splits are fetched from it. It had a 3-day outage 2026-07-26..29. On 2026-10-21 it was unreachable from Ali's laptop network and also from an outside vantage point. | open | troubleshooting "OpenML unreachable from the laptop's network" | First thing on any new box: `curl -m 20 https://www.openml.org/api/v1/json/task/3913`. Before a long sweep, pre-fetch every task's data into the cache (one `caml run` per task with a tiny budget, or a small prefetch command), so an outage mid-sweep can't fail jobs. |
| KI-06 | `scripts/sync_vps.sh` and `scripts/sync_local.sh` don't delete files on the target that were deleted locally. | open (minor) | both scripts' headers | Re-provision from scratch if a stale file ever matters. |

## Verification gaps (code exists, never proven live)

| ID | Item | Status | Details | Next action |
|---|---|---|---|---|
| KI-10 | GPU: the `HOME` env fix for the SIGILL (exit 132) on the first cold-cache CUDA run. | fixed, unverified | troubleshooting "SIGILL (exit 132)", `operations/gpu.md` | Next GPU box (the laptop's RTX 3060 qualifies): clean `~/.nv`, cold `caml run TabPFN`. |
| KI-11 | GPU: AutoGluon and LightAutoML never run on GPU. The `cu124` default wheel index was never checked against a second driver. | unverified | `operations/gpu.md` | Next GPU box. **Ali's laptop has an RTX 3060 6GB (driver 580)** that could close KI-10/11 (reinstall the 3 torch frameworks with GPU wheels). |
| KI-12 | TPOT's `FeatureUnion`-nested selector extraction has never been observed in a live fit. | unverified | troubleshooting 2026-09-15 | A longer or wider TPOT run; the pilot's `christine`/`cnae-9` may trigger it. |
| KI-14 | *(Parked 2026-10-21: local runs abandoned.)* Local storage redirection: nothing CAML writes should land on the laptop's system disk. Verified for the orchestrator venv and uv cache (system-disk free space unchanged). Not yet checked after real framework runs, in particular H2O's `ice_root` and Ray's session dir (both via `TMPDIR`) and TabPFN weights (via `XDG_CACHE_HOME`). | in progress | `operations/local-storage.md` | After the install and smoke runs: compare `df /`, check `/tmp` and `~/.cache` for new CAML-related dirs. |
| KI-13 | `caml compare` with 3+ frameworks (Friedman + Holm post-hoc) has never run on real sweep data (unit tests with hand-verified answers only). | unverified | `docs/reference/cli.md` | Run it on the pilot results. |
| KI-15 | The local-file dataset path (`caml prepare-data` → `caml run`/`sweep` → `caml leaderboard`) is tested end to end only with a scikit-learn stand-in framework, never with a real AutoML framework (added 2026-10-24; before that, local CSVs didn't load at all under pandas 3). | unverified | `docs/reference/cli.md` (prepare-data), troubleshooting 2026-10-24 | On the pilot VPS: `prepare-data` a public CSV (e.g. an OpenML dataset exported to CSV) and sweep 2-3 frameworks under `quick`. |
| KI-16 | `camlctl` (new in 1.1.0) has run only on GitHub's Ubuntu 24.04 runner standing in for a VPS (CI's `server-e2e`: root over SSH to 127.0.0.1, setup from the pushed commit, dataset intake, prepare-data, FLAML install and sweep, status, bundle, stop), and in unit tests as an ordinary user. It hasn't run on a real VPS. Also untested: the `ubuntu`-sudoer login route (camlctl re-running itself with `sudo -n`), `setup` cloning from GitHub instead of a pushed archive, and `stop` on a full multi-framework sweep. | fixed, unverified | troubleshooting "Windows, macOS and Linux as the operator machine", `skills/caml-benchmark/references/camlctl.md` | The paper pilot VPS: run the documented flow (`CAML_E2E_SOURCE=github tests/e2e/agent_flow.sh caml-vps` on a disposable box), then the pilot itself through camlctl. |
| KI-17 | The Windows and macOS operator flows are checked in CI (commands, line endings, ssh config parsing, argument passing; `tests/operator/`), but no agent has yet driven a real run from Windows or macOS. | unverified | the operator profiles, `docs/getting-started/agent-prompt.md` | Field reports: a Mac user's (via Ali), and Ali's own Windows run. Fold every problem they record into the profiles, camlctl and troubleshooting. |

## Upstream framework limitations (documented, not CAML bugs)

| ID | Framework | Issue | Details |
|---|---|---|---|
| KI-20 | NaiveAutoML | `KeyError: nan` in its own `fit()` on every task; **skipped from the roster** (Ali's call, 2026-07-30). | `frameworks/naiveautoml.md` |
| KI-21 | AutoGluon 1.5.0 | Its own `fastai`/`fastcore` pin breaks the `NeuralNetFastAI` model on every job. AutoGluon routes around it, so one model type never contributes. | `frameworks/autogluon.md` |
| KI-22 | SapientML | On `diabetes130US`, its *generated* pipeline raises `KeyError: 'str_catg_False'` at predict time. | `operations/e2e-verification.md` |
| KI-23 | GAMA | On wide data (`bioresponse`, 1776 cols) under a 60s budget: `IndexError` in `postprocessing/best_fit.py`. Its search evaluated zero individuals. Upstream bug and budget mismatch combined. | `STATUS.md` (2026-09-15) |
| KI-24 | TPOT | On `dresses-sales`: "No individuals could be evaluated in the initial population". Undetermined whether it's the budget or a preprocessing gap. | `frameworks/tpot.md` |

## Hardware / budget limits (not bugs)

| ID | Item | Details |
|---|---|---|
| KI-30 | Local `TabPFN` refuses more than 1000 samples on CPU (TabPFN-3 guard), so it fails 6/9 `validation` tasks on CPU boxes. Lifting the guard unconditionally was requested and **deferred** together with the GPU work. | `frameworks/tabpfn.md` |
| KI-31 | FEDOT OOM-killed (7.4GB RSS) on `census-income` on a 7.8GB box. | `operations/e2e-verification.md` |
| KI-33 | *(Moot since 2026-10-21: local runs abandoned, back to a VPS.)* The local laptop as a benchmark box: 4C/8T i7-11370H, 15GB RAM with about 5GB free during normal desktop use, a USB HDD over NTFS-FUSE, and a shared, thermally throttled desktop. With no `max_mem_size_mb` set, each job's memory budget is whatever is free at that moment, so it varies between jobs. Fine for the pilot (finding bugs); paper-grade runs need a fixed memory budget, an idle machine, and the hardware reported. | `operations/local-storage.md` |
| KI-32 | 2GB-RAM boxes can't run even one wide real dataset safely. Use at least 8GB (32GB for the paper sweeps). | `docs/operations/.vps-access.local.md` (local), `docs/research/paper-plan.md` |

## Decisions needed (Ali)

| ID | Decision | Why it matters |
|---|---|---|
| KI-41 | **TabPFN-3 weights are non-commercial**: get a legal read before publishing results that use local `TabPFN`. | Publication counts as results leaving internal use. |
| KI-42 | **`TabPFNClient` sends data to Prior Labs' API**. Proposed: exclude it from the paper's main comparison. | Fairness (off-box compute) and data egress. |
| KI-43 | Should `caml run` default to keep-going (AMLB's behavior) instead of abort? Currently opt-in via `--keep-going`. | Abort-by-default silently loses failed jobs from `results.csv`. |
| KI-44 | Which paper claim(s) to pursue (A: installability, B: modern head-to-head, C: feature usage). | Shapes the main sweep's design. See `docs/research/paper-plan.md`. |

## Cosmetic (recorded so nobody chases them)

- FLAML/MLJAR pull `nvidia-nccl-cu12` (~289MB) via xgboost on CPU boxes; it's
  unused (troubleshooting, Phase 2).
- The per-fold "Metric scores" debug log shows `duration: nan`, but
  `results.csv` has the real durations (CLAUDE.md, Phase 2).

## Recently closed

| Date | Item | Commit |
|---|---|---|
| 2026-10-24 | `provision_vps.sh`/`sync_vps.sh` failed on macOS (GNU-only `mktemp --suffix`, `tar --transform` in `lib_package.sh`). Portable rewrite; `tests/test_lib_package.py` includes a BSD-strict shim test, and CI runs it on macOS. | `v1.0.1` |
| 2026-10-24 | `prepare-data` on spreadsheet exports: semicolon CSVs (confusing "target not found"), decimal commas (would become categories), non-UTF-8 files (traceback). Separator detection, decimal commas, a clear encoding error. | `v1.0.1` |
| 2026-10-24 | KI-40 decided: CAML is **Apache-2.0** (Ali: "i agree with both the license and having two separate repos"). MIT, like AMLB, was the alternative. | `v1.0.0` |
| 2026-10-24 | KI-47 decided: **two repos**. The public `A1i-Tabatabaei/CAML` starts from a fresh history at `v1.0.0`; the full development history (which held server details and personal notes that don't belong in public) stays in the private archive `A1i-Tabatabaei/CAML-private`. | `v1.0.0` |
| 2026-10-24 | Local CSV datasets never loaded under pandas 3 (`dtypes[i]` → `dtypes.iloc[i]` in `datasets/file.py`). Verified by `tests/test_file_dataset_pipeline.py`. | this release |
| 2026-10-24 | `caml run --keep-going` crashed (`None < 1` formatting a failed row's duration) instead of writing the error row. Verified with a failing stand-in framework. | this release |
| 2026-10-24 | `app_version` never carried the revision (`0.1.0-dev` on every row; the 2026-10-21 REVISION fix below never reached it). Now `1.0.0 [branch, sha(+worktree)]`. | this release |
| 2026-10-24 | `caml install --all` stopped at the first failed framework; it now continues and lists the failures. | this release |
| 2026-10-21 | KI-46: stale July venvs (`frameworks/FLAML/venv`, `frameworks/MLJARSupervised/venv`, plus their `.setup` markers) deleted and `~/.cache/uv` cleared (Ali: "yes delete them"). The system disk gained about 2GB net, since part of the uv cache was hardlinked into still-used envs. Ali's uv tools (colab, colab-mcp, mobilerun) were checked and still work; the dev `.venv` was kept and the unit tests still pass. | (no code) |
| 2026-10-21 | KI-45 decided: run the AMLB install audit on the laptop (Ali: "it's ok"). Only Docker's own layers touch the system disk; the AMLB clone, venvs, pip cache and TMPDIR are bind-mounted onto the drive. | `35677e5` |
| 2026-10-21 | `caml doctor` measured free space on `/` instead of the workspace's filesystem; verified on the drive workspace (665.5GB). | `35677e5` |
| 2026-10-21 | `caml run` aborting the whole batch on one failure and leaving no row for it. The root cause is the hardcoded `exit_on_job_failure=True`; it's now opt-out via `--keep-going`. **Live verification: KI-01.** | `35677e5` |
| 2026-10-21 | No fixed seed across separate invocations (`seed: auto`). Added `--seed`. | `35677e5` |
| 2026-10-21 | `app_version` = `dev [NA, NA]` on VPS checkouts. Fixed with a `REVISION` file. *(Incomplete: `git_info` got the fallback, but `app_version` ignored it until 2026-10-24.)* | `35677e5` |
| 2026-10-21 | Code updates never reaching an existing VPS checkout. Added `scripts/sync_vps.sh`. | `35677e5` |
| 2026-09-15 | `run_subprocess` StaleProcessError race. | `0be1a35` |
| 2026-09-15 | TPOT/GAMA feature-usage structural gaps (FeatureUnion, leading imputer). | `0be1a35` |
| 2026-09-10 | LightAutoML feature-usage attribute (`collect_used_feats()`). | `0be1a35` |
