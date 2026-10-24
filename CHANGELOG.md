# Changelog

All notable changes to CAML. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). The day-by-day engineering record
is in [STATUS.md](STATUS.md) and [CLAUDE.md](CLAUDE.md).

## [1.0.1] - 2026-10-24

### Fixed

- **`scripts/provision_vps.sh` and `scripts/sync_vps.sh` failed on macOS** at
  their first step. The packaging helper (`scripts/lib_package.sh`) used
  GNU-only `mktemp --suffix` and `tar --transform`, which macOS's BSD tools
  don't have, so the README's setup command didn't work from a Mac. It now
  stages the files in a temp directory instead, and runs on the stock
  `/bin/bash` 3.2.
- **`caml prepare-data` and spreadsheet exports**: a semicolon-separated CSV
  (Excel's format in many locales) failed with a confusing "target not
  found, did you mean f1;f2;label?", and a non-UTF-8 export crashed with a
  `UnicodeDecodeError` traceback. The separator (`,` `;` tab `|`) is now
  detected from the header line, decimal commas are read in semicolon files,
  and a non-UTF-8 file gets an error with the `iconv` command that fixes it.

### Added

- `docs/getting-started/agent-prompt.md`: a prompt to hand an AI agent, so
  it benchmarks your dataset on your VPS and monitors the run, from a Mac.
- CI runs the packaging helper and `prepare-data` tests on macOS too.

### Changed

- CI: `actions/checkout` v4 → v7 and `astral-sh/setup-uv` v6 → v7, both on
  Node 24 (GitHub deprecated Node 20 for actions).

## [1.0.0] - 2026-10-24

First public release, under the Apache License 2.0.

### Frameworks

- 11 framework integrations verified end to end on real Ubuntu servers:
  AutoGluon 1.5.0, H2O AutoML 3.46.0.11, LightAutoML 0.4.2,
  MLJAR-supervised 1.3.1, FLAML 2.6.0, TPOT 1.1.0 (rewritten for TPOT's
  2025 API), GAMA 23.0.0.post1, FEDOT 0.7.5, TabPFN 8.1.0 (local), the
  TabPFN client 0.3.3 (hosted), and SapientML 0.4.17. NaiveAutoML 0.1.6 is
  skipped because of an upstream bug.
- Each framework runs in its own `uv` venv with its own Python and exact
  pins, declared in a `framework.toml` manifest.

### Commands

- `caml install`, `status`, `doctor`, `run`, `uninstall`, `check-versions`.
- `caml sweep`: frameworks × tasks × folds as isolated, resumable,
  shardable jobs, with every failure classified in a ledger.
- `caml compare`: Wilcoxon, or Friedman plus Holm-corrected pairwise tests,
  across datasets.
- **New:** `caml prepare-data` turns one CSV/TSV/Parquet file into
  stratified folds and a benchmark YAML. It always writes the task type
  explicitly and records provenance (`dataset.json`).
- **New:** `caml leaderboard` ranks frameworks per dataset (mean ± std across
  folds, folds succeeded, training time), with optional Markdown output.
- **New:** the `quick` constraint (5 minutes per job, all cores) for first
  screenings.
- `caml install --all` now continues past a failed framework and lists the
  failures at the end, instead of stopping at the first one.

### Fixed

- **Local CSV datasets never loaded** under pandas 3: the file loader looked
  up dtypes by position (`dtypes[i]`), which pandas 3 no longer supports.
  Found by the new end-to-end test of the local-file path.
- **`caml run --keep-going` crashed on the first failed job** instead of
  recording it. A failed job's row has no duration, and the formatter
  compared `None < 1`. The same code exists upstream in AMLB.
- **`app_version` never recorded the code revision**: every row said
  `0.1.0-dev`. It now reads like `1.0.0 [main, 3eb1cf7]`, from git or from the
  `REVISION` file that deploys carry.
- Sweeps on a YAML path get a readable default name (`churn-quick`).
- Removed two pandas-4 deprecations in the file loader.

### Added for users and agents

- `skills/caml-benchmark/`: an Agent Skill that takes an AI agent, or a
  person, from a dataset to a reported comparison. It covers the VPS, data
  preparation, TabPFN, sweeps, triage, reporting and citation. It installs
  as a Claude Code plugin (`/plugin marketplace add A1i-Tabatabaei/CAML`).
- A redesigned README with a banner and diagrams that read on GitHub's dark
  theme, plus `AGENTS.md`, `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`
  and CI.

[1.0.1]: https://github.com/A1i-Tabatabaei/CAML/releases/tag/v1.0.1
[1.0.0]: https://github.com/A1i-Tabatabaei/CAML/releases/tag/v1.0.0
