# GAMA

**Verified 2026-07-30 — came up clean well within the time-box.** See `STATUS.md`.

| | |
|---|---|
| PyPI package | [`gama`](https://pypi.org/project/gama/) (pinned `23.0.0.post1`) |
| GitHub | [amore-labs/gama](https://github.com/amore-labs/gama) (renamed from `openml-labs/gama`, originally `PGijsbers/gama`) |
| License | Apache-2.0 (see license discrepancy note below) |
| Python range | `>=3.11,<3.12` — forces exactly 3.11 (see below) |
| System deps | none |

## Why it's in the roster, cautiously

General automated ML assistant from the OpenML ecosystem lineage — natural
fit for an AMLB-inspired harness, but health signals are weaker than every
other framework in the v1 roster (see below).

## Known context (see `CLAUDE.md`) — **provisional, time-box this one**

- Re-confirmed live, 2026-07-30 (health flag still accurate, now over two
  years stale rather than the ~1.5 years it was at the original
  2026-07-17 research pass): last PyPI release is still `23.0.0.post1`
  (2024-06-14), last GitHub push 2024-09-04, repo not archived. The PyPI
  listing still has **no** `home_page`/`project_urls`/`author` metadata.
- Time-box the install attempt in Phase 5. If it doesn't install/run
  cleanly, downgrade to best-effort/`blocked` in `STATUS.md` rather than
  absorbing unbounded debugging time — get the user's explicit sign-off
  on that trade-off before making the call.

## License discrepancy — confirmed live, 2026-07-30

`gama`'s own `pyproject.toml` declares `license = {text = "MIT"}`, but the
actual `LICENSE` file at the repo root is the Apache License 2.0 —
confirmed two independent ways (GitHub's own license detection, and
reading the file directly). This is an inconsistency in the upstream
project itself, not a research error here. The actual `LICENSE` file is
treated as authoritative (it's the real grant; the `pyproject.toml` field
is just informational metadata that can drift), matching this project's
existing "Apache-2.0" classification.

## Python version cap — real, not the PyPI classifiers

`gama`'s `pyproject.toml` declares `requires-python = ">=3.9"` with no
ceiling, but the real constraint is transitive, confirmed live
(2026-07-30) against `gama==23.0.0.post1`'s actual `pyproject.toml`:

- `gama` hard-pins `scikit-learn>=1.1.0,<1.3`. The newest release under
  that ceiling, `scikit-learn 1.2.2`, has wheels for cp38–cp311 only — no
  cp312, no cp313 at all (that scikit-learn release line ended before
  Python 3.12 existed). This is a full Python version lower than
  [FEDOT](fedot.md)'s or [LightAutoML](lightautoml.md)'s `<3.13` ceilings.
- `category-encoders>=1.2.8`, `stopit>=1.1.1`, `liac-arff>=2.2.2`,
  `black==24.3.0`, `psutil` are all pure-Python or have wide wheel
  coverage — not additional risks.

`[python].range = ">=3.11,<3.12"` forces resolution to exactly 3.11.

## API drift check against AMLB's reference — none found

Verified live against `github.com/amore-labs/gama` (tag `v23.0.0.post1`,
`gama/gama.py`'s base `Gama` class plus `GamaClassifier`/`GamaRegressor`),
2026-07-30: `n_jobs`, `max_total_time`, `scoring`, `random_state`,
`max_memory_mb`, `output_directory` are all still valid `Gama.__init__`
keyword arguments; `.fit(X, y)`, `.predict(X)`, `.predict_proba(X)`
signatures and the private `_final_pop` attribute (used for
`models_count`, confirmed still set at the end of `fit()`) are all
unchanged.

AMLB's own reference has a `version_leq_20_2_0` branch handling a GAMA API
that predates version `20.2.0` — dropped entirely rather than ported dead,
since CAML's exact-pin-and-deliberately-bump policy will never install
anything that old. AMLB's own `GAMA/setup.sh` also has a one-off
`scikit-learn<1.3` re-install specifically for version `"23.0.0"` (not
`.post1`), commented as being for "the fixed version for the 2023Q2
definition" — AMLB-side benchmark-versioning legacy, not needed here since
`gama`'s own `pyproject.toml` already pins `scikit-learn<1.3` directly.

`exec.py` is therefore a near-verbatim port of AMLB's own
`frameworks/GAMA/exec.py`, including its already-present
`measure_inference_time` wiring (unlike FEDOT's older reference, GAMA's
AMLB integration already had this) — **not independently re-verified**:
it uses `dataset.test.X.sample(...)` (pandas-style) rather than
TPOT/FEDOT's numpy-index-based synthetic-row construction, and this
wasn't cross-checked against CAML's actual runtime `dataset.test.X` type
since `measure_inference_time` defaults off and isn't exercised by the
test benchmark. Revisit if Phase 6 turns that flag on.

## Verification status

Verified on the real VPS, 2026-07-30 — came up clean well within the
time-box. Two real install bugs found and fixed; zero `exec.py` bugs.
The health flag above turned out not to translate into an actual bring-up
problem — worth remembering that a stale/thin-metadata package can still
just work.

### Install bugs (2, both fixed)

**1. `numpy<2` steering pin** — importing `gama` itself raised `ValueError:
numpy.dtype size changed, may indicate binary incompatibility. Expected 96
from C header, got 88 from PyObject`, from `sklearn.utils.murmurhash` (a
Cython extension). `gama`'s own `scikit-learn<1.3` pin resolves to
`scikit-learn==1.2.2`, which predates numpy 2.0 (released ~Jan 2023 vs.
numpy 2.0's June 2024) — its compiled extensions were built against
numpy's pre-2.0 C-API, and `gama`'s unbounded `numpy>=1.20.0` floor
doesn't stop a numpy 2.x runtime from being installed alongside it. Same
class of fix as [H2OAutoML](h2o.md)'s identical pin — third framework in
the roster needing it, and the first where the ABI break is the *direct*
cause rather than a supporting-library constraint.

**2. `setuptools<82` steering pin** — surfaced one import deeper once fix
\#1 cleared the crash above: `ModuleNotFoundError: No module named
'pkg_resources'`, from `gama.gama`'s `import stopit` (`stopit/__init__.py`
does a bare `import pkg_resources`). This is the *same* `stopit` package
that caused [TPOT](tpot.md)'s original instance of this bug, and the same
root cause as TPOT's and [FEDOT](fedot.md)'s identical fixes: a bare `uv
venv` doesn't bundle `setuptools`, and `setuptools>=82.0.0` dropped
`pkg_resources` entirely even when present. Third framework in the roster
needing this exact pin.

### Smoke-test scores (6/6 jobs, kc2/iris/cholesterol × 2 folds)

| Task | Fold | Metric | Score |
|---|---|---|---|
| kc2 | 0 | AUC / acc / balacc / logloss | 0.890 / 0.811 / 0.646 / 0.342 |
| kc2 | 1 | AUC / acc / balacc / logloss | 0.887 / 0.792 / 0.500 / 0.480 |
| iris | 0 | acc / logloss | 0.933 / 0.091 |
| iris | 1 | acc / logloss | 1.000 / 0.011 |
| cholesterol | 0 | RMSE / MAE / R² | 42.14 / 32.92 / 0.083 |
| cholesterol | 1 | RMSE / MAE / R² | 53.96 / 43.15 / -0.010 |

All in line with every other verified framework in the roster. `caml
doctor` clean afterward; `tests/test_e2e_framework_run.py` passing
alongside the rest of the installed roster (see `STATUS.md`).

### Non-blocking observation

`models_count` reports `50` identically on every single job (all 6, both
folds, all 3 tasks) — GAMA's internal `_final_pop` attribute apparently
reflects something closer to total individuals evaluated across the whole
evolutionary-algorithm run within the time budget, not just the final
generation's population size. Consistent, not a bug, just a less
informative signal for GAMA than e.g. TPOT's `evaluated_individuals`
count. Not investigated further.
