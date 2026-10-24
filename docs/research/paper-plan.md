# Paper track: plan, decisions and status

**Started 2026-10-20.** Ali asked where a paper about CAML could be
published (peer-reviewed and not), what arXiv takes, and what CAML still
needs before a paper is worth writing; then said "proceed with your plan"
(2026-10-21). This page is the durable record of that plan. Update it as
phases complete. Open problems live in `operations/known-issues.md`.

## Status at a glance

| Phase | What | Status |
|---|---|---|
| 0 | Pick the paper's claim(s); related-work check | **in progress**: candidates below; decision KI-44 |
| 1 | Sweep infrastructure (`caml sweep`, `--keep-going`, `--seed`, provenance) | **done locally, 2026-10-21**: unit-tested; live run pending (KI-01) |
| 2 | Pilot sweep: all frameworks × `pilot` benchmark; triage every failure | **ready to launch**: waiting on Ali's VPS (the local-laptop attempt was abandoned 2026-10-21 because of the network) |
| 2b | Claim-A experiment: AMLB install audit in clean containers | **scripts ready**; runs on the VPS after the framework installs |
| 3 | Validity checks (agreement with AMLB's published results, fairness protocol) | not started |
| 4 | Main sweep (multi-box) | not started; sized from pilot timings |
| 5 | Analysis (CD diagrams, ranks, failure and runtime tables) | not started (`caml compare` already does the tests) |
| 6 | Release readiness (license, public repo, Zenodo DOI, reproduce script, arXiv endorser) | in progress (2026-10-24): **public** as `A1i-Tabatabaei/CAML` v1.0.0 under Apache-2.0, with README, `CITATION.cff`, agent skill and CI. Zenodo (Ali switches it on; it archives the next release), the reproduce script and the endorser are still to do. |

## Candidate claims (Phase 0)

A plain "we re-ran AMLB with newer versions" paper is incremental. The
candidates, roughly strongest first:

- **A. Installability and maintenance decay.** Measure, rather than
  assert, whether the original AMLB still installs and runs each
  framework when you follow its own docs on a clean machine, versus CAML's
  uv-plus-pinned-manifest approach. It's cheap (no big compute), novel-ish,
  and matches why CAML exists. Experiment: `scripts/research/` (see below).
- **B. A significance-tested head-to-head of current framework versions**
  on the AMLB suites (openml.org/s/271 and /269), with honest failure
  reporting (`caml sweep` ledger) and Demšar-style statistics (`caml compare`).
- **C. Feature-usage audit**: which input columns each framework's final
  model actually uses. Only worth a section if the pilot shows real
  variation; most frameworks may report "all columns".

**Related-work check still to do**: AMLB's JMLR paper (Gijsbers et al.,
JMLR 25(101), 2024) and newer "living" tabular benchmarks (TabArena, as I
recall; verify it exists and what it covers), so we don't claim
something already shown.

## Where to publish (researched 2026-10-20)

| Venue | Type | Fit / requirements |
|---|---|---|
| AutoML Conference, **ABCD track** (Applications, Benchmarks, Challenges, Datasets) | peer-reviewed, PMLR | Best fit. 9 pages, a mandatory reproducibility review, and code must be public and downloadable in one click. The 2026 deadline was Apr 30 (extended to May 14), and the conference was in Ljubljana, Sep 28–Oct 1. The 2027 call isn't out; one aggregator *estimates* mid-March 2027. |
| JMLR | peer-reviewed journal | Strong precedent: AMLB itself was published there (vol. 25, 2024). |
| TMLR | peer-reviewed, rolling | Double-blind on OpenReview, judges correctness over significance. No extended versions of conference papers; arXiv/workshop overlap is OK. |
| NeurIPS Evaluations & Datasets track (renamed from Datasets & Benchmarks) | peer-reviewed | Wants evaluation studied as a science. The 2026 cycle has passed. |
| JMLR MLOSS / JOSS / SoftwareX | software papers | All require an **OSI/open license**. MLOSS also wants evidence of a user community. JOSS papers mustn't be about research results. |
| arXiv, Zenodo, non-archival workshops | not peer-reviewed / light | See below. Zenodo gives a citable DOI for the code release. |

**Gate for every peer-reviewed venue: an open license and a public repo.**
Both met since 2026-10-24: CAML is Apache-2.0 and public at
https://github.com/A1i-Tabatabaei/CAML (v1.0.0). The TabPFN-3 weights are
non-commercial (KI-41).

Sources: [AutoML 2026 CfP](https://groups.google.com/g/coseal/c/P4epSYWznq0),
[AMLB in JMLR](https://jmlr.org/papers/v25/22-0493.html),
[TMLR policies](https://www.jmlr.org/tmlr/editorial-policies.html),
[NeurIPS 2026 E&D](https://neurips.cc/Conferences/2026/CallForEvaluationsDatasets),
[JMLR MLOSS](https://jmlr.org/mloss/mloss-info.html),
[JOSS](https://joss.readthedocs.io/en/latest/submitting.html).

## arXiv (researched 2026-10-20)

- **Free**: "There are no fees or costs for article submission"
  ([about](https://info.arxiv.org/about/index.html)).
- **Not peer review**: moderators check that the paper is scholarly and in
  scope, not that it's correct. Since Oct 31, 2025, CS *surveys and
  position papers* need prior peer-review acceptance. A research article
  with experiments (this paper) is unaffected.
- **Endorsement is required for a first submission** (policy since
  2026-01-21): either an institutional email *plus* a prior arXiv paper in
  the domain, or a **personal endorsement from an established arXiv author**
  in that area. Ali has no prior arXiv paper, so the realistic route is a
  personal endorser. Ask one person at a time, not a mass email.
  **Start looking early: it's the least predictable step.**
  ([policy](https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/))
- Must be LaTeX source with a full English version. Significant
  generative-AI use in the text must be disclosed (this project is built
  with Claude, so disclose if AI helps draft the text).
- **Timing**: submitted by 14:00 US Eastern on a weekday → announced 20:00
  ET the same day. Holds "mostly" clear within 48h but can take days to
  weeks. Limits: 2 new submissions/month, 3 active.
- **Personal/jurisdiction notes** (network reachability, export-control
  questions for co-authors and endorsers) are kept out of the public repo,
  in the gitignored `docs/research/.paper-plan-private.local.md`.
- License choice is irrevocable. CC BY 4.0 allows the widest reuse, and
  the arXiv non-exclusive license is the safest for later journal
  submission.

## Hardware

- **Pilot box: back to a VPS (2026-10-21, later still).** The laptop
  attempt below was abandoned the same day: OpenML was unreachable from
  Ali's network, and downloads ran at about 2 MB/s. Ali will provide a VPS
  with the "requested" spec further down.
- **Laptop attempt (2026-10-21, abandoned): Ali's laptop.** Ali chose not to
  rent the VPS below, to save money. Specs: i7-11370H 4C/8T, 15GB RAM
  (about 5GB free in normal use), RTX 3060 Laptop 6GB (installed CPU-only
  for the pilot), Ubuntu 24.04. Everything lives on an external 1TB USB HDD
  (NTFS) because the system disk has about 13GB free. Setup, checks and
  caveats: `operations/local-storage.md`. Consequences: the pilot runs one
  job at a time, so it takes longer (estimate below). Per-job memory varies
  with desktop use (KI-33). Pilot timings are therefore a rough guide for
  sizing the main sweep, not a measurement to publish.
- **Pilot box (requested 2026-10-21, superseded the same day)**: 8 *dedicated* x86_64 vCPU (no
  shared/burstable plans, because CPU steal distorts time-budgeted results),
  **32GB RAM**, 150–200GB SSD, Ubuntu 24.04, no GPU. Why: FEDOT was
  OOM-killed at 7.4GB on a 7.8GB box (KI-31); 10 venvs take ~15–30GB of
  disk; AMLB's paper used 8 vCPU/32GB machines (as recalled, verify). CPU-only
  because only 3 of 10 frameworks can use a GPU, and AMLB was CPU-only.
- **Estimated VPS time for the pilot phase: about 1 week**, made up of half
  a day of setup and installs, 1–2 days for the pilot sweep, 1–3 days of
  bug-fix re-runs, and half a day for the AMLB audit. Then delete it after
  copying `results.csv` and the ledgers back.
- **Main sweep**: 2–3 more *identical* boxes (same provider, plan and
  region). Sized after the pilot.

## Pilot design (Phase 2)

- Benchmark `resources/benchmarks/pilot.yaml`: 9 tasks from the official
  AMLB suites (6 classification from /s/271, 3 regression from /s/269),
  each chosen to exercise one risk (categoricals, true/false labels,
  wide data, many classes, 49k rows, heavy missingness). IDs and stats were
  read from the OpenML API on 2026-10-21.
- Constraint `pilot`: 2 folds, 600s, 4 cores (the same shape as `test`, but
  a distinct name: KI-03).
- 10 frameworks × 9 tasks × 2 folds = **180 jobs**, at most about 30 hours
  of budget, run via `caml sweep` (`operations/sweeps.md`). On the laptop,
  jobs run one at a time, so expect about 30–40 hours of wall-clock with
  the machine kept awake (`run_local_detached.sh` blocks sleep). The sweep
  resumes from its ledger, so it can run in overnight chunks
  (`--max-jobs`).
- Exit criterion: every failure triaged into a CAML bug (fixed),
  upstream (documented), or limit (documented), plus measured per-job wall
  time and RAM to size the main sweep.

## Claim-A experiment: AMLB install audit (Phase 2b)

`scripts/research/run_amlb_install_audit.sh` (on the VPS, as root) runs
`amlb_install_audit_inner.sh` in throwaway `ubuntu:22.04` (the OS AMLB's
docs support) and `ubuntu:24.04` (current LTS) containers, limited to
4 CPU / 16GB. It follows AMLB's `docs/getting_started.md` literally:
documented prerequisites only, `--branch stable`, venv, `pip install -r
requirements.txt` (plus the docs' sequential fallback), then
`runbenchmark.py <fw> test test -s only` and `-s skip` for each framework,
with RandomForest as a control. Output is `audit.csv`
(env, framework, step, status, seconds, detail) plus per-step logs. The CAML
side of the comparison is `caml install` + `caml run --benchmark test` on the
bare VPS (its supported path). Docker is used only as a clean room for
measuring AMLB; it isn't part of CAML (locked decision #2 is unchanged).

## Compute estimates for the main sweep (rough, before measuring)

Job-hours at 4 cores per job, before about 20–30% overhead (a guess):

| Design | Jobs | Job-hours |
|---|---|---|
| 16 tasks × 10 frameworks × 10 folds × 10 min | 1,600 | ~267 |
| same at 1h | 1,600 | ~1,600 |
| 39 tasks × 10 frameworks × 10 folds × 1h | 3,900 | ~3,900 |

## Decisions log

- 2026-10-24: **open-source CAML** (Ali: "I need you to open-source it and
  make it public", after a README redesign, an agent skill and release
  prep; "make it ready to publish for now"). Prepared: Apache-2.0
  (confirmed by Ali the same day, KI-40), version 1.0.0,
  `CITATION.cff`, `skills/caml-benchmark/`, CI, and a scrub of personal
  details from the public tree (the jurisdiction notes moved to the
  gitignored `.paper-plan-private.local.md`). The skill tells agents that
  write up CAML results to cite CAML **and tell the user** they did, and
  `CITATION.cff` provides GitHub's "Cite this repository" button.
  Published the same day as a fresh public repo; the full history stays
  private (KI-47).
- 2026-10-21 (later): **run locally instead of on a VPS** (Ali: "keep
  everything installed in there so i don't have to pay a lot of money for
  vps"). Installs are allowed on the laptop only under
  `/mnt/MIRC/CAML-STORAGE` (the external drive); nothing new goes on the
  system disk. This supersedes the "never locally" rule in the next entry.
  The pilot installs and runs with `CAML_COMPUTE=cpu` (AMLB's CPU-only
  protocol), even though the laptop has a GPU.
- 2026-10-21 (latest): **local abandoned, back to a VPS** (Ali: "forget
  about local as my network is trash. i'll provide the vps"). The local run
  was stopped and its files deleted at Ali's request.
- 2026-10-21: Ali approved running the AMLB install audit (claim A) on the
  laptop's Docker (moot now: it runs on the VPS). If something can't go on the drive, the system disk is
  an allowed fallback. Commit at stable states at my discretion (commits
  only; pushing wasn't mentioned).

- 2026-10-21: proceed with the plan (Ali). All installs and runs happen on
  a VPS, never locally (standing rule). Documentation is the top
  priority: everything gets written down as it happens (Ali).
- 2026-10-21: `caml run`'s default (abort on failure) left unchanged.
  Keep-going is opt-in, and `caml sweep` always uses it (KI-43).
