# E2E reliability verification (2026-07-31)

A from-scratch teardown → redeploy → test-everything reliability audit of
the full 11-framework roster, run entirely through the committed scripts
(`scripts/teardown_workspace.sh`, `scripts/provision_vps.sh`,
`scripts/verify_e2e.sh`) with no manual intervention. Re-runnable: the
same three scripts reproduce this on any fresh box.

## What was tested

Every framework was run against **two** benchmarks under the `test`
runtime constraint:

- **`test`** (3 tasks) — the existing clean smoke test: kc2 (binary),
  iris (multiclass), cholesterol (regression).
- **`validation`** (9 tasks) — real data-quality/type edge cases ported
  verbatim from AMLB's own `validation.yaml`: many-feature numeric
  (bioresponse), mostly-categorical-with-missing-values (dresses-sales),
  mixed-with-missing (eucalyptus), high-dimensional near-binary
  (internet-advertisements), many-feature multiclass (micro-mass),
  boolean-`(true,false)`-target (kc1), target-not-in-last-column
  (APSFailure), badly-formatted-missing-values (diabetes130US), and
  many-categoricals-with-whitespace-labels (census-income). See
  `resources/benchmarks/validation.yaml`.

## Headline result

**Teardown + redeploy worked cleanly, purely from the documented
process.** `teardown_workspace.sh` deleted the entire 7.9GB workspace
(without touching the `caml` user, `TABPFN_TOKEN`, or the apt baseline);
`provision_vps.sh` rebuilt it from a fresh `git archive` of `HEAD`;
`caml install --all` then reproduced **every** framework at exactly the
pin and Python version recorded in `STATUS.md`, with `caml doctor` green
before and after. This is positive evidence the docs/scripts are
self-sufficient, not just descriptive.

**On clean data (`test` benchmark), 10 of 11 frameworks pass**; only
NaiveAutoML fails, on its already-documented confirmed-upstream bug.

**On messy data (`validation` benchmark), the roster splits clearly** —
7 frameworks handle all 9 real-world-messiness tasks without a single
crash; 3 more choke on specific messy-data tasks; NaiveAutoML fails
everywhere. This is exactly what the experiment was for: the clean
smoke test hid robustness differences that only messy data exposes.

## Results matrix

| Framework | `test` (3 tasks) | `validation` (9 tasks) | Notes |
|---|---|---|---|
| AutoGluon | PASS | **PASS (9/9)** | clean |
| FLAML | PASS | **PASS (9/9)** | clean |
| GAMA | PASS | **PASS (9/9)** | clean |
| H2OAutoML | PASS | **PASS (9/9)** | clean |
| LightAutoML | PASS | **PASS (9/9)** | clean |
| MLJARSupervised | PASS | **PASS (9/9)** | clean |
| TabPFNClient | PASS | **PASS (9/9)** | clean (hosted API, server-side) |
| FEDOT | PASS | FAIL (7/9) | kc1 boolean-label + census-income OOM |
| SapientML | PASS | FAIL (7/8, aborted) | diabetes130US generated-pipeline `KeyError` |
| TPOT | PASS | FAIL (1/2, aborted) | dresses-sales "no individuals evaluated" |
| NaiveAutoML | FAIL | FAIL (0/1, aborted) | confirmed-upstream `KeyError: nan` |

"7/9" = 7 of 9 validation tasks produced a real, non-NaN score. "aborted"
means a hard subprocess crash cancelled that framework's remaining tasks
in the run (see "Job-runner abort behavior" below), so the denominator
is how far it got, not all 9.

The `TabPFNClient` row is the hosted-API TabPFN (its name during this audit
was just `TabPFN`). The **local `TabPFN`** framework — which runs the model
on-box — was added afterward (2026-07-31) and is **not** in this audit's
matrix; it passes the `test` benchmark. Its own `validation` run (2026-08-01)
found **3/9 pass**: on a CPU box TabPFN-3 refuses datasets larger than 1000
samples by default, so 6 of the 9 fail on that hardware guard — **not** on
messy data (the three ≤1000-row tasks pass cleanly, matching the client's
robustness). Full detail in `docs/frameworks/tabpfn.md`.

## Failure analysis

### NaiveAutoML — fails on both benchmarks (known, already documented)

Already skipped in the roster (`STATUS.md`, `docs/frameworks/naiveautoml.md`).
Fails on the very first task of both benchmarks with the confirmed-upstream
`KeyError: nan` in `naiveautoml`'s own
`get_config_space_for_selected_algorithms`. This run **reproduced the
documented behavior exactly** — a good consistency signal, not a new
problem. Not a CAML bug; nothing to fix here.

### FEDOT — 7/9 validation tasks, two distinct failures

1. **`kc1` — `ResultError: y contains previously unseen labels:
   np.str_('0.0')`.** `kc1`'s target is boolean `(true, false)`; AMLB's
   own `validation.yaml` explicitly warns this trips frameworks that let
   pandas coerce `"true"/"false"` strings to `True/False` booleans and
   back. This is the **same class of bug** fixed in SapientML's `exec.py`
   this project (label round-tripping), surfacing here in FEDOT's
   integration. Plausibly fixable in `frameworks/FEDOT/exec.py` with
   explicit string-dtype enforcement on the prediction/truth columns —
   **not attempted in this pass** (the mandate was to run the documented
   process and record what happens, not to make new code changes
   mid-audit). Flagged for a future FEDOT-specific fix.
2. **`census-income` — OOM-killed (exit 137).** Confirmed via `dmesg`: a
   7.4GB-RSS Python process SIGKILL'd on this 7.8GB-RAM box, timestamp-
   matched to the second. `census-income` is large with many
   high-cardinality categoricals; FEDOT's in-memory footprint exceeded
   the box. This is a **resource-limit finding, not a code bug** — it
   would plausibly pass on a larger box (relevant to the Phase 8 GPU/
   bigger-instance work). Not fixable at the CAML layer without capping
   FEDOT's memory or moving to a bigger instance.

### SapientML — 7/8 validation tasks, generated-pipeline bug on messy data

Failed on **`diabetes130US`** ("missing values not formatted correctly")
with `KeyError: 'str_catg_False'` raised **inside SapientML's own
generated pipeline code** — the synthesized pipeline references a derived
categorical-encoding column (`str_catg_False`) that doesn't exist at
predict time. This is a SapientML-internal robustness gap on
badly-formatted-missing-value data, not something CAML's `exec.py`
controls (it's in the code SapientML *generates*). The
`AttributeError: predict_proba is not available when probability=False`
lines earlier in the same log are the known-benign SVC candidate-skip
noise (SapientML routes around a failed candidate internally), **not**
the fatal error — the `KeyError` is. Documented as an upstream limitation;
not fixable from the integration side.

### TPOT — aborted after 2 tasks, "no individuals could be evaluated"

Failed on **`dresses-sales`** (mostly-categorical with missing values in
most columns) with TPOT's own `Exception: No individuals could be
evaluated in the initial population` — TPOT's genetic search couldn't fit
a single valid pipeline within the short `test`-constraint budget on this
messy, heavily-categorical dataset. Could be a too-tight time budget for
TPOT's search on hard data, or a genuine preprocessing gap; distinguishing
the two would need a longer-constraint re-run (`1h4c` instead of `test`).
Documented; not chased further in this pass.

## Job-runner abort behavior (worth knowing)

`caml run <fw> --benchmark validation` **stops running that framework's
remaining tasks after certain hard failures** (a subprocess crash /
SIGKILL / uncaught exception surfaces as a `CancelledError: Job ... was
interrupted`), rather than isolating the one failure and continuing. This
is why TPOT shows "1/2" (aborted after `dresses-sales`, never reached the
other 7) and SapientML "7/8" (aborted on `diabetes130US`, never reached
`census-income`), while FEDOT — whose two failures were "softer" (a
returned error result, not a crash) — ran all 9. Consequence: a
benchmark-level `FAIL` can undercount how many tasks a framework would
actually clear. To get a true per-task picture for a partly-failing
framework, re-run the survivors with `--task` scoped runs (see
`docs/reference/cli.md`). Recorded here as observed behavior, not
labelled a bug — whether "abort the batch" vs. "isolate and continue" is
the right default is a design question for the user, not a unilateral
change.

## End state

`caml doctor` clean after the full run: no stray H2O JVMs, 204GB disk
free, all apt packages present. The resumed portion (5 frameworks) ran
09:42–11:35 UTC; the full experiment spanned two sessions (the first was
interrupted by a tooling bug, see below).

## Tooling bugs found and fixed *during* the audit

Both in the verification harness itself, both fixed and pushed:

1. **Undetached remote process.** `verify_e2e.sh` was first launched over
   a live `ssh ... "bash scripts/verify_e2e.sh"` pipe. When the driving
   session ended, the dropped SSH connection SIGHUP'd the run mid-flight
   (after 6 of 11 frameworks had completed — results preserved). Fixed:
   the script is now resumable (pass an existing results dir; recorded
   combos are skipped) and its header documents launching it detached
   (`setsid nohup ... & disown`).
2. **Resume skip-set silently matched nothing.** `DONE["$fw\t$bench"]=1`
   (quoted) vs. `${DONE[$fw\t$bench]}` (unquoted) build different keys —
   bash strips the backslash from an unquoted `\t`. The first resume
   attempt was about to blindly re-run ~8h of already-good results;
   caught before it did. Switched the key delimiter to `::`. See
   `docs/operations/troubleshooting.md`.

## Re-running this

```bash
scripts/teardown_workspace.sh root@<host>      # wipe workspace (keeps creds/apt)
scripts/provision_vps.sh      root@<host>      # rebuild from committed HEAD
# then, ON the box, detached:
ssh root@<host> "sudo -iu caml bash -lc '
  cd ~/caml-workspace/CAML &&
  setsid nohup bash scripts/verify_e2e.sh > /tmp/verify_e2e.log 2>&1 < /dev/null & disown'"
# resume an interrupted run by passing its results dir as $1 to verify_e2e.sh
```

## Turning this into a significance comparison

Once ≥2 frameworks have real `validation`-benchmark rows in
`output/results.csv` (this audit produces exactly that), `caml compare`
turns the pass/fail matrix above into an actual statistical comparison:

```bash
caml compare TPOT GAMA LightAutoML --benchmark validation --constraint test
```

Check the `excluded_tasks` list in its output against this doc's own
pass/fail matrix — a framework that aborted partway through `validation`
(e.g. TPOT on `dresses-sales`, see the matrix above) has no row for that
task, so `compare` correctly excludes it from the paired comparison rather
than guessing. See `docs/reference/cli.md` for the full command reference.
