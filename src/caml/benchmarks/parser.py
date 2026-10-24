# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

from __future__ import annotations

from typing import List, Tuple

from .openml import is_openml_benchmark, load_oml_benchmark
from .file import load_file_benchmark
from caml.utils import str_sanitize, Namespace


def benchmark_load(
    name: str, benchmark_definition_dirs: List[str]
) -> Tuple[Namespace | None, List[Namespace], str | None, str]:
    """Loads the benchmark definition for the 'benchmark' cli input string.

    :param name: the value for 'benchmark'
    :param benchmark_definition_dirs: directories in which benchmark definitions can be found
    :return: a tuple with constraint defaults, tasks, the benchmark path (if it is a local file) and benchmark name
    """
    # Identify where the resource is located, all name structures are clearly defined,
    # but local file benchmark can require probing from disk to see if it is valid,
    # which is why it is tried last.
    if is_openml_benchmark(name):
        benchmark_name, benchmark_path, tasks = load_oml_benchmark(name)
    else:
        benchmark_name, benchmark_path, tasks = load_file_benchmark(
            name, benchmark_definition_dirs
        )

    file_defaults = next((task for task in tasks if task.name == "__defaults__"), None)
    tasks = [task for task in tasks if task is not file_defaults]
    for t in tasks:
        t.name = str_sanitize(t.name)
    return file_defaults, tasks, benchmark_path, str_sanitize(benchmark_name)
