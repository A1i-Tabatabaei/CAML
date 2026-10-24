# Installing the orchestrator

CAML's orchestrator (the `caml` CLI itself, distinct from any individual
AutoML framework) needs `uv` and Python ≥3.11.

```bash
# 1. Install uv (also used later by scripts/bootstrap_vps.sh)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone CAML
git clone <CAML repo url>
cd CAML

# 3. Sync the orchestrator's own dependencies (click, pydantic, pandas,
#    scikit-learn, openml, ...) into .venv/ — this is separate from any
#    framework's own venv under frameworks/<Name>/venv/
uv sync

# 4. Sanity check
uv run caml --help
uv run pytest
```

`uv sync` installs `caml` itself in editable mode, so `uv run caml ...`
always reflects the current source tree with no rebuild step.

Next: `vps-bootstrap.md` to prepare a fresh Ubuntu server for actually
installing and running frameworks.
