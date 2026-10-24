# MLJAR-supervised

| | |
|---|---|
| PyPI package | [`mljar-supervised`](https://pypi.org/project/mljar-supervised/) |
| GitHub | [mljar/mljar-supervised](https://github.com/mljar/mljar-supervised) |
| License | MIT |
| Current pin | `1.3.1` |
| Python range | `>=3.11,<3.13` |
| System deps | `build-essential`, `swig` (apt) |
| Status | see `STATUS.md` |

## Why it's in the roster

Second reference implementation for the plugin contract — still simple
(pure pip once system deps are present), used to confirm the pattern
generalizes beyond FLAML before tackling anything harder (JVM, torch, API
rewrites).

## Integration notes

`exec.py` is ported near-verbatim from AMLB's
`frameworks/mljarsupervised/exec.py` — `AutoML().fit()`'s API hasn't
changed since AMLB's original integration (confirmed against v1.3.1,
2026-07-17). matplotlib is forced to the `agg` backend (no display on a
headless VPS).

## Gotchas

- Needs `build-essential` + `swig` at the system level (declared in
  `framework.toml`'s `[install.system_packages]`, also covered by
  `scripts/bootstrap_vps.sh`'s baseline apt install).
- Boolean-target prediction handling has a known quirk for
  mljar-supervised ≤0.10.6 ([mljar/mljar-supervised#442](https://github.com/mljar/mljar-supervised/issues/442)) —
  `exec.py` still special-cases it; harmless no-op on 1.3.1 but kept for
  safety.
- **Transitive dependency resolution trap (discovered during Phase 1
  scaffolding, 2026-07-17)**: `mljar-supervised==1.3.1` depends on
  `shap>=0.46.0`, which on Linux depends on **unconstrained** `numba` and
  `llvmlite`. Without another package in the same `uv pip install` pinning
  either one, `uv`'s resolver backtracks all the way to
  `llvmlite==0.36.0` — which hard-fails to build on Python ≥3.10
  (`RuntimeError: Cannot install on Python version 3.12.12; only versions
  >=3.6,<3.10 are supported`). Confirmed: `shap==0.52.0`'s own metadata
  places no version bound on `numba`/`llvmlite` for non-Apple-Silicon
  platforms, so nothing else in the tree steers the resolver toward a
  modern release. **Fix**: `framework.toml` adds `numba>=0.60` as an
  explicit steering constraint alongside `mljar-supervised==1.3.1` in the
  same install command — forces a modern numba, which drags a compatible
  llvmlite (~0.43+) along with it. This is exactly the class of failure
  the per-framework isolated-venv + exact-pin design exists to catch and
  fix once, in one place, rather than every user hitting it independently.

## Last verified

**2026-07-18, dev sandbox (Ubuntu 24.04.4, matches VPS target OS)** — not
yet re-verified on the real VPS (Phase 2+, see `STATUS.md`). Full
`caml install mljarsupervised && caml run mljarsupervised --benchmark test --constraint test`
completed cleanly (exit 0), all 6 jobs (kc2/iris/cholesterol × 2 folds)
produced real, plausible scores, e.g. kc2 fold 1: `auc=0.9188`,
`acc=0.8868`.

Also hit and fixed a pandas-3.0 compatibility bug in shared orchestrator
code (not MLJAR-specific — see `docs/operations/troubleshooting.md`):
pandas 3.0 defaults string columns to Arrow-backed dtypes, so
`preds["label"].values` returned an `ArrowStringArray` instead of a plain
`numpy.ndarray`, which the cross-venv result serialization didn't
recognize (`NoResultError: Object of type ArrowStringArray is not JSON
serializable`). Fixed centrally in
`src/caml/utils/serialization.py::is_serializable_data`/`serialize_data`.
