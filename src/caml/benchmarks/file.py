# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

import logging
import os
from typing import List, Tuple, Optional

from caml.utils import config_load, Namespace

log = logging.getLogger(__name__)


def _find_local_benchmark_definition(
    name: str, benchmark_definition_dirs: List[str]
) -> str:
    # 'name' should be either a full path to the benchmark,
    # or a filename (without extension) in the benchmark directory.
    if os.path.exists(name):
        return name

    for bd in benchmark_definition_dirs:
        bf = os.path.join(bd, f"{name}.yaml")
        if os.path.exists(bf):
            # We don't account for duplicate definitions (yet).
            return bf

    # should we support s3 and check for s3 path before raising error?
    raise ValueError(
        f"Incorrect benchmark name or path `{name}`, name not available in {benchmark_definition_dirs}."
    )


def load_file_benchmark(
    name: str, benchmark_definition_dirs: List[str]
) -> Tuple[str, Optional[str], List[Namespace]]:
    """Loads benchmark from a local file."""
    benchmark_file = _find_local_benchmark_definition(name, benchmark_definition_dirs)
    log.info("Loading benchmark definitions from %s.", benchmark_file)
    tasks = config_load(benchmark_file)
    benchmark_name, _ = os.path.splitext(os.path.basename(benchmark_file))
    for task in tasks:
        if task["openml_task_id"] is not None and not isinstance(
            task["openml_task_id"], int
        ):
            raise TypeError("OpenML task id for task {task.name!r} must be integer.")
    return benchmark_name, benchmark_file, tasks
