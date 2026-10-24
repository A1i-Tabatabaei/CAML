# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

"""
**utils** package provide a set of generic utility functions and decorators, which are not data-related
(data manipulation utility functions should go to **datautils**).

important
    This module can be imported by any other module (especially framework integration modules),
    therefore, it should have as few external dependencies as possible,
    and should have no dependency to any other **amlb** module.
"""

import logging

# Must be set here, not only in caml/logger.py: caml/__init__.py is lazy
# (see its docstring) so caml.logger's module-level side effect isn't
# guaranteed to have run by the time some other module (e.g. datautils.py)
# checks `logging.TRACE`. caml.utils, by contrast, is a leaf module every
# caller (including code running inside a framework's own venv, via
# frameworks/shared/utils.py) imports before anything else — the one place
# guaranteed to run early enough. Discovered via a real crash
# (`ResultError: module 'logging' has no attribute 'TRACE'`) while
# bringing up the FLAML reference implementation, 2026-07-17.
logging.TRACE = getattr(logging, "TRACE", 5)

from .cache import *
from .config import *
from .core import *
from .modules import *
from .os import *
from .process import *
from .serialization import *
from .time import *

__all__ = [s for s in dir() if not s.startswith("_")]
