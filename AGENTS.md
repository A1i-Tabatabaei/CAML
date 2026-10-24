# AGENTS.md

Instructions for AI coding agents working **in** this repository. If your task
is to **use** CAML to benchmark someone's dataset, follow
[`skills/caml-benchmark/SKILL.md`](skills/caml-benchmark/SKILL.md) instead.

## What this is

CAML benchmarks open-source AutoML frameworks, each in its own isolated `uv`
environment, behind one CLI (`caml`). The orchestrator lives in `src/caml/`.
Each framework integration lives in `frameworks/<Name>/` (a `framework.toml`
manifest, an `__init__.py` that crosses the subprocess boundary, and an
`exec.py` that runs inside the framework's own venv). Benchmarks and
constraints live in `resources/`.

## Read first

- [`STATUS.md`](STATUS.md): the live state and what's in progress.
- [`CLAUDE.md`](CLAUDE.md): the full decision log, with locked architecture
  decisions that need the maintainer's sign-off to change.
- [`docs/operations/known-issues.md`](docs/operations/known-issues.md): every
  open bug, unverified fix and upstream limitation.

## Rules

1. **Don't install AutoML frameworks on a development machine.**
   `caml install` and real framework runs happen on a VPS
   (`scripts/provision_vps.sh`). Code, docs and unit tests are fine locally.
2. **Run the tests**: `uv run pytest -q`. They need no framework installed;
   `tests/test_e2e_framework_run.py` skips itself unless one is.
3. **Document as you go.** Every bug (fixed or not), feature and result goes
   into the docs when it happens: bugs in
   `docs/operations/troubleshooting.md` and the known-issues register,
   features in their reference doc plus the README, and code adapted from
   AMLB in `NOTICE.md`.
4. **Never commit secrets**: no tokens, passwords or server addresses.
   Private notes go in gitignored `*.local.md` files.
5. **Adding a framework**: follow
   [`docs/contributing/adding-a-framework.md`](docs/contributing/adding-a-framework.md).
   Pin an exact version, and verify on a real server before calling it
   verified.
6. Match the surrounding code's style. Ported AMLB files keep their
   attribution headers.
7. **Keep the agent docs runnable from every OS.** Operators run Windows,
   macOS or Linux; CAML runs only on the Ubuntu server, driven by
   `scripts/camlctl`. A server command in the docs is
   `ssh <host> camlctl <plain words>`, or one pair of double quotes with no
   `$`, backtick, `%`, `!` or `"` inside. `tests/test_agent_docs.py`
   enforces this, and keeps the three prompts (README and
   `docs/getting-started/agent-prompt.md`) identical. Per-OS details belong
   in `skills/caml-benchmark/references/operator-*.md`. Server-side scripts
   must keep LF line endings (`.gitattributes`).
8. **Field reports** (`caml-field-report-<os>.md`, from users' agents) are
   bug reports: fold each problem into the code, the operator profiles,
   troubleshooting and known-issues.
