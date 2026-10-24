# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

"""caml entrypoint package.

Lazy re-exports (PEP 562 module ``__getattr__``), unlike AMLB's
``amlb/__init__.py`` which imports ``Resources``/``Benchmark`` eagerly.
That matters here specifically: every framework's ``exec.py`` runs inside
its own *minimal* venv (just ``frameworks/shared/requirements.txt`` —
numpy/pandas/pyarrow/psutil, no ``openml`` client, no orchestrator deps)
and imports the leaf module ``caml.utils`` (via
``frameworks/shared/utils.py``). Importing any submodule of a package
always executes that package's ``__init__.py`` first — so an eager
``from .resources import Resources`` here (which chains into
``caml.benchmarks.openml`` -> ``import openml``) would make
``ModuleNotFoundError: No module named 'openml'`` crash *every* framework
subprocess, since the OpenML client package is never installed into a
framework's own venv. Confirmed this is a real, reproducible failure
(not just theoretical) while bringing up the FLAML reference
implementation, 2026-07-17 — see NOTICE.md and
docs/operations/troubleshooting.md.
"""

from .__version__ import __version__

__all__ = [
    "log",
    "AutoMLError",
    "Resources",
    "Benchmark",
    "SetupMode",
    "TaskResult",
    "__version__",
]


def __getattr__(name):
    if name == "log":
        from .logger import app_logger

        return app_logger
    if name == "AutoMLError":
        from .errors import AutoMLError

        return AutoMLError
    if name == "Resources":
        from .resources import Resources

        return Resources
    if name in ("Benchmark", "SetupMode"):
        from .benchmark import Benchmark, SetupMode

        return {"Benchmark": Benchmark, "SetupMode": SetupMode}[name]
    if name == "TaskResult":
        from .results import TaskResult

        return TaskResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
