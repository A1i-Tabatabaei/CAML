# FLAML

| | |
|---|---|
| PyPI package | [`flaml[automl]`](https://pypi.org/project/FLAML/) |
| GitHub | [microsoft/FLAML](https://github.com/microsoft/FLAML) |
| License | MIT |
| Current pin | `2.6.0` |
| Python range | `>=3.11,<3.13` |
| System deps | none |
| Status | see `STATUS.md` |

## Why it's in the roster

Simplest healthy framework in the v1 set — pure `pip install`, no system
dependencies, small dependency tree. Chosen as the **first reference
implementation** for the `framework.toml` + `installer.py` plugin contract
precisely because its simplicity isolates plugin-contract bugs from
framework-specific bugs.

## Integration notes

`exec.py` is ported near-verbatim from AMLB's `frameworks/flaml/exec.py` —
FLAML's `AutoML().fit()` API hasn't changed since AMLB's original
integration (confirmed against FLAML 2.6.0, 2026-07-17). Metric mapping
(`acc→accuracy`, `auc→roc_auc`, etc.) unchanged.

## Gotchas

- AMLB's old `setup.sh` pinned `xgboost<2` for FLAML 1.2.4 specifically
  (a much older release). Not carried forward here — CAML pins FLAML
  2.6.0. Re-check if `current_pin` is ever moved back below 2.x.

## Last verified

**2026-07-17, dev sandbox (Ubuntu 24.04.4, matches VPS target OS)** — not
yet re-verified on the real VPS (Phase 2+, see `STATUS.md`). Full
`caml install flaml && caml run flaml --benchmark test --constraint test`
completed cleanly (exit 0), all 6 jobs (kc2/iris/cholesterol × 2 folds)
produced real, plausible scores, e.g. kc2 fold 0: `auc=0.8755`,
`acc=0.7736`, `logloss=0.3682`.

Two real bugs surfaced and fixed while bringing this framework up (both in
shared orchestrator code, not FLAML-specific — see
`docs/operations/troubleshooting.md` for the full writeups):
`caml/__init__.py`'s eager imports broke every framework subprocess's
`caml.utils` import (fixed via lazy PEP 562 `__getattr__`), and
`DataFrame.append()` (removed in pandas 2.0) in `results.py`'s global
results aggregation (fixed via `pd.concat`).
