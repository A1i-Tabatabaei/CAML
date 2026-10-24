# Adding a framework

The recipe for bringing up a new framework, replacing AMLB's
`docs/extending/framework.md`. See `architecture/framework-plugin-contract.md`
for the full manifest schema this recipe produces.

## 1. Check the roster rationale first

Is this framework already evaluated in `CLAUDE.md`'s research findings?
If not, check: is it actively maintained (recent commits/releases)? What
license (flag GPL/AGPL for legal review — see `CLAUDE.md`'s license
section for how CAML has handled LGPL/attribution-clause cases so far)?
Pure `pip install`, or does it need Java/R/.NET/a compiler toolchain?

## 2. Scaffold the directory

```
frameworks/<Name>/
├── framework.toml    # see architecture/framework-plugin-contract.md for the schema
├── __init__.py       # run() delegating to run_in_venv() — copy an existing
│                      # simple framework's __init__.py (FLAML's is the
│                      # shortest reference) and adjust only if the
│                      # framework needs anything beyond train/test X/y
└── exec.py            # the actual framework call, running inside the venv
```

`__init__.py` pattern (unchanged from FLAML/MLJARSupervised — only copy
different if the framework needs different `input_data`, e.g. TabPFN-style
foundation models sometimes need extra fields):

```python
def run(dataset, config):
    from frameworks.shared.caller import run_in_venv

    data = dict(
        train=dict(X=dataset.train.X, y=dataset.train.y),
        test=dict(X=dataset.test.X, y=dataset.test.y),
        problem_type=dataset.type.name,
    )
    return run_in_venv(__file__, "exec.py", input_data=data, dataset=dataset, config=config)
```

`exec.py` must define `run(dataset, config)` returning
`frameworks.shared.callee.result(...)`, and end with:

```python
if __name__ == "__main__":
    from frameworks.shared.callee import call_run
    call_run(run)
```

## 3. Write `framework.toml`

Pin `current_pin` to whatever's genuinely latest on PyPI **today**, not an
old number carried over from anywhere else (see
`architecture/version-pinning-policy.md`). Declare `[python].range` from
the package's PyPI classifiers/`requires_python` — but verify empirically
on the VPS, classifiers are a hint, not ground truth (see `STATUS.md`'s
research table for examples where they were wrong, e.g. H2O/FEDOT).
Declare any `apt` system packages needed.

## 4. Local dry run (no VPS needed for pure-pip frameworks)

```bash
uv run caml install <name>
uv run caml status          # confirm it shows "verified"
uv run caml run <name> --benchmark test --constraint test --mode test
```

## 5. VPS verification

Follow `operations/vps-runbook.md`'s per-framework loop: tracking issue →
install → smoke test → fix/iterate → doc page → `STATUS.md` update.

## 6. Write the doc page

`docs/frameworks/<name>.md` — see `docs/frameworks/flaml.md` for the
template (PyPI package, license, current pin, Python range, system deps,
gotchas log, last-verified-on-VPS date). Add it to `mkdocs.yml`'s nav.

## 7. Update `STATUS.md`

Flip the framework's row to `verified`, fill in pinned version / Python /
date / issue number.
