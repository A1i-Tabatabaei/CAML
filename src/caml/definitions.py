# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

"""Small dataclasses shared between resources.py and benchmark.py.

Trimmed from AMLB's ``amlb/frameworks/definitions.py``: the AWS-only
``ec2_volume_type`` field is dropped (CAML has no AWS runner), and
``max_mem_size_mb`` is promoted onto the constraint itself since local runs
need it to size things like the H2O JVM.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskConstraint:
    name: str
    folds: int
    max_runtime_seconds: int
    cores: int
    max_mem_size_mb: int | None = None
    min_vol_size_mb: int | None = None
