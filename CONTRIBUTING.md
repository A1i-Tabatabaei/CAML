# Contributing to CAML

Thanks for helping. Bug reports, framework integrations, fixes and
documentation are all welcome.

## Reporting a problem

Open an issue with:

- the command you ran and the full error (or the tail of the job log in
  `output/sweeps/<sweep>/logs/`);
- `uv run caml status` and `uv run caml doctor` output;
- the server's OS, vCPU and RAM;
- for a framework failure: the dataset (an OpenML task id, or a small
  sample that reproduces it).

Check [`docs/operations/known-issues.md`](docs/operations/known-issues.md)
and [`docs/operations/troubleshooting.md`](docs/operations/troubleshooting.md)
first: many framework failures are known upstream limitations.

Report security issues privately; see [SECURITY.md](SECURITY.md).

## Development setup

```bash
git clone https://github.com/A1i-Tabatabaei/CAML.git && cd CAML
uv sync                 # the orchestrator's own environment (small)
uv run pytest -q        # about 160 tests in a couple of minutes; no AutoML framework needed
```

Don't run `caml install` on your workstation: the frameworks are tens of
GB. Install and run them on a disposable Ubuntu 24.04 server
(`scripts/provision_vps.sh root@HOST`), and use `scripts/sync_vps.sh` to
push your working tree there (`INCLUDE_WORKTREE=1` includes uncommitted
changes).

## Pull requests

- **Tests**: add or update tests for any behavior change. Orchestrator logic
  should be testable without a framework; `tests/test_file_dataset_pipeline.py`
  shows how to run the real pipeline with a scikit-learn stand-in.
- **Docs in the same PR.** CAML's rule is that every bug, fix and feature
  is written down when it happens: troubleshooting entries for bugs, the
  known-issues register for anything still open, the CLI reference and the
  README for features.
- **Adding or bumping a framework**: follow
  [`docs/contributing/adding-a-framework.md`](docs/contributing/adding-a-framework.md).
  Pins are exact. Say which server you verified on, and paste the
  `caml run <Name> --benchmark test --constraint test` scores.
- **Code adapted from AMLB** keeps its attribution header and gets an entry in
  [`NOTICE.md`](NOTICE.md).
- Style: match the surrounding code. New modules should pass `uv run ruff check <file>`.
- Never commit secrets, server addresses or datasets.

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
