# H2O AutoML

| | |
|---|---|
| PyPI package | [`h2o`](https://pypi.org/project/h2o/) |
| GitHub | [h2oai/h2o-3](https://github.com/h2oai/h2o-3) |
| License | Apache-2.0 |
| Current pin | `3.46.0.11` |
| Python range | `>=3.9,<3.12` (H2O-3 only documents support up to 3.11) |
| System deps | `openjdk-17-jre-headless` |
| Status | see `STATUS.md` |

## Why it's in the roster

Long-standing JVM-backed AutoML (stacked ensembles over GBM/GLM/DRF/XGBoost/
DeepLearning), included in AMLB since its earliest versions. The first
framework in CAML's roster with a real runtime dependency outside the Python
package itself — a JVM child process — which is why it got its own phase
(Phase 4) rather than riding along with the rest of Tier 1.

## Integration notes

Ported from AMLB's `frameworks/H2OAutoML/exec.py` (`automlbenchmark-reference/`)
fairly closely — H2O's `h2o.init()` / `H2OAutoML` / `.leaderboard` API hasn't
had a breaking rewrite the way TPOT's did. Two things were deliberately
trimmed, not because they were wrong, but because CAML doesn't need them:

- **Dropped the ARFF single/double-quote retry heuristic.** AMLB's original
  `exec.py` passed through whatever raw format (ARFF or CSV) OpenML happened
  to hand back, then had a version-gated retry loop to cope with ARFF's
  ambiguous string-quoting rules (`h2o>=3.32.1` vs. older). CAML's dataset
  accessors let a framework request an explicit format up front —
  `dataset.train.data_path("csv")`, the same pattern AutoGluon uses for
  `"parquet"` — so `__init__.py` always requests CSV and `exec.py` never
  needs to guess. `escapechar="\\"` is kept (general CSV-escaping robustness,
  not ARFF-specific); the `quotechar` retry dance and the `packaging` import
  that existed only to version-gate it are both gone.
- **Dropped the opt-in `BackendMemoryMonitoring` hook.** It depended on
  `config.ext.monitoring`, a piece of AMLB's monitoring subsystem CAML never
  ported (no other framework's `exec.py` here uses it either).

Data flow: `dataset.train.path` / `dataset.test.path` (CSV files) plus
`dataset.target.index`, loaded directly into H2O via `h2o.import_file()` —
H2O works on its own `H2OFrame` abstraction, not CAML's `X`/`y` arrays or a
parquet path, so this is a third data-flow shape alongside FLAML/MLJAR's
array-based and AutoGluon's parquet-path patterns.

## Gotchas

- **Python ceiling: H2O-3 only documents support for Python up to 3.11.**
  Confirmed live against `docs.h2o.ai/h2o/latest-stable/h2o-docs/faq/python.html`,
  2026-07-30: "Python 3.7.x, 3.8.x, 3.9.x, 3.10.x, 3.11.x" — no 3.12/3.13
  anywhere, unlike every other Tier-1 framework in this roster so far (PyPI's
  own `requires_python` metadata is just `>=3.7`, which doesn't communicate
  the real ceiling). `framework.toml` pins `<3.12` so `uv`'s newest-first
  resolution lands on 3.11 rather than 3.12/3.13, which aren't verified to
  work. Installed and ran cleanly on 3.11.15.
- **`numpy<2` is a real, documented H2O-3 requirement**, not just a CAML
  quirk: "H2O-3 only supports numpy<2" (same FAQ page). H2O's own PyPI
  metadata doesn't declare numpy as a dependency at all (it mainly moves
  data over REST + its own `H2OFrame`, only touching pandas/numpy at the
  `.as_data_frame()` boundary) — but CAML's `frameworks/shared/requirements.txt`
  installs `numpy>=1.26` (→ numpy 2.x) into every framework venv before the
  framework's own packages run. Added `numpy<2` as an explicit steering pin
  in `[install].packages`, same class of fix as MLJARSupervised's
  `numba>=0.60` and TPOT's `setuptools<82`. Confirmed working: install logs
  show numpy resolving to 2.4.6 via the shared requirements step, then being
  downgraded to 1.26.4 once H2O's own package step ran.
- **First framework needing an apt system package** (`openjdk-17-jre-headless`).
  `src/caml/frameworks/installer.py`'s `_ensure_apt_packages()` (via
  `sudo -n apt-get install`) and the `caml` user's NOPASSWD sudoers entry for
  `apt-get install` (`scripts/bootstrap_vps.sh`) were both written in Phase 0
  anticipating this — worked cleanly on the first real attempt, no changes
  needed. Java 17 was chosen because H2O-3 documents support for "Java SE 17,
  16, 15, ..., 8" — 17 is the newest version actually in the supported set,
  and Ubuntu 24.04's default archives don't carry `openjdk-8-jdk` (the
  version AMLB's own `setup.sh` hardcodes) at all.
- **JVM lifecycle**: `h2o.init()` spawns a local `java` child process running
  `h2o.jar` (bundled inside the `h2o` wheel itself — the 254MB download size
  is mostly this jar, not Python code). `exec.py`'s `finally` block calls
  `h2o.connection().close()` then `.local_server.shutdown()` — ported as-is
  from AMLB, which already gets this right — so a job timeout, exception, or
  crash doesn't leave an orphaned `java` process behind. `caml doctor`
  already has a `pgrep -f h2o.jar` stray-process check (built in Phase 0,
  ahead of this framework landing); confirmed clean (`stray H2O JVM
  processes: none`) immediately after the verification run below.
- Each of the 6 smoke-test jobs booted its own local H2O cluster from a
  fresh JVM (~2s startup each, visible in the run log as "Attempting to
  start a local H2O server..." / "H2O session ... closed") rather than
  reusing one cluster across jobs — matches AMLB's per-job `h2o.init()`
  design. Fine at this scale (6 tiny jobs); worth knowing if a much larger
  benchmark run's wall-clock ever looks JVM-startup-dominated.

## Last verified

**2026-07-30, real VPS (Ubuntu 24.04, 4 vCPU/7.8GB RAM/232GB disk)** —
`caml install H2OAutoML && caml run H2OAutoML --benchmark test --constraint test`
completed cleanly on the first attempt (no bugs found, unlike every other
Tier-1 framework so far — the shared installer/manifest infrastructure had
already absorbed the general lessons from AutoGluon/TPOT). All 6 jobs
(kc2/iris/cholesterol × 2 folds) produced real, plausible scores in line
with every other verified framework:

- kc2: AUC 0.866 / 0.873
- iris: acc 1.000 / 1.000, logloss 0.024 / 0.010
- cholesterol: RMSE 45.47 / 54.72

`caml doctor` confirmed no stray H2O JVM processes after the run. Also
confirmed via `tests/test_e2e_framework_run.py`, run together with
AutoGluon and TPOT (all three installed frameworks at the time) — 3
passed in 1108s.
