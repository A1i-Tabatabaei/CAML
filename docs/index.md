# CAML

CAML is an open-source (Apache-2.0), near-100%-automated AutoML benchmark
harness for Ubuntu cloud servers. It benchmarks the major frameworks on the
OpenML suites or on your own data (`caml prepare-data`, `caml leaderboard`;
see the README and `skills/caml-benchmark/SKILL.md`). It runs the *latest* versions of popular
open-source AutoML frameworks, each isolated in its own `uv`-managed Python
environment. 11 framework integrations are verified and working —
AutoGluon, H2O AutoML, FLAML, MLJAR-supervised, TabPFN (local) and
TabPFNClient (hosted API), TPOT, LightAutoML, FEDOT, GAMA, SapientML.
NaiveAutoML was attempted and skipped (confirmed-upstream bug). TabPFN is
offered in two variants: **`TabPFN`** runs the foundation model 100%
on-box (data never leaves the machine), while **`TabPFNClient`** uses
Prior Labs' hosted API for boxes with no local compute. See the
per-framework pages under **Frameworks** in the nav, or `STATUS.md` in the
repo for live status.

## Relationship to AMLB

CAML is a modernized, from-scratch rewrite inspired by
[OpenML's AutoML Benchmark](https://github.com/openml/automlbenchmark)
(AMLB), MIT licensed. AMLB's core idea — one sandboxed environment per
framework, orchestrator and framework communicating over a stdin/JSON
subprocess boundary — is solid and is kept. What's replaced:

| AMLB | CAML | Why |
|---|---|---|
| stdlib `venv` + `pip`, Python pinned via the `deadsnakes` PPA | `uv` (interpreter provisioning + venv + package install) | No apt/PPA dependency at all; eliminates a whole class of "wrong Python" install failures on modern Ubuntu |
| Per-framework hand-rolled `setup.sh` + central `resources/frameworks.yaml` | Declarative `framework.toml` manifest per framework + one shared `installer.py` | AMLB's own maintainers flagged this duplication (issues [#64](https://github.com/openml/automlbenchmark/issues/64), [#642](https://github.com/openml/automlbenchmark/issues/642)) |
| `version: "stable"` = `pip install -U` at install time (no lockfile) | Exact-pin-and-deliberately-bump | Reproducibility; this is literally how TPOT's 2025 breaking rewrite silently broke AMLB's integration |
| Docker/Singularity/AWS runners | Bare-metal venv only | Single Ubuntu VPS target, not a cluster |

See `architecture/overview.md` for the full picture, and the project's
`NOTICE.md` for a file-by-file provenance ledger.

## Quickstart

```bash
git clone https://github.com/A1i-Tabatabaei/CAML.git && cd CAML
uv sync
uv run caml doctor
uv run caml install flaml
uv run caml run flaml --benchmark test --constraint test
```

For a fresh Ubuntu VPS, run `scripts/bootstrap_vps.sh` as root first — see
`getting-started/vps-bootstrap.md`.
