# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.
#
# Trimmed from AMLB's amlb/utils/modules.py: dropped `pip_install`/
# `pip_main` (runtime `pip install` via the `pip` internal API) — unused
# elsewhere in CAML, and exactly the kind of ad hoc install path that
# `caml.frameworks.installer` (uv-based) replaces. `uv`-managed venvs
# don't ship `pip` preinstalled by default, so this failed to even import.

import sys
import types

__no_export = set(dir())  # all variables defined above this are not exported


def register_module(module_name):
    if module_name not in sys.modules:
        mod = types.ModuleType(module_name)
        sys.modules[module_name] = mod
    return sys.modules[module_name]


def register_submodule(mod, name):
    fullname = ".".join([mod.__name__, name])
    module = register_module(fullname)
    setattr(mod, name, module)


__all__ = [s for s in dir() if not s.startswith("_") and s not in __no_export]
