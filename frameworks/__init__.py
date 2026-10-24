"""
The **frameworks** directory holds one subpackage per AutoML framework.
Each framework subpackage exposes:

- ``run(dataset, config)``: required. Called by a job to run the framework
  against the given ``Dataset``/``TaskConfig``. Implemented by delegating
  to ``exec.py`` inside the framework's own isolated venv, via
  ``frameworks.shared.caller.run_in_venv`` — see that module's docstring
  for the isolation mechanism.

Installation is *not* handled here — see ``framework.toml`` (declarative
manifest) and ``src/caml/frameworks/installer.py`` (the shared installer
that reads it), which together replace AMLB's per-framework ``setup.sh``.
"""
