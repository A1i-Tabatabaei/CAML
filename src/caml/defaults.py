# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

import pathlib

import openml

from caml.utils import Namespace as ns

# https://github.com/openml/automlbenchmark/pull/574#issuecomment-1646179921
try:
    cache_directory = openml.config.cache_directory
except AttributeError:
    cache_directory = openml.config.get_cache_directory()

default_dirs = ns(
    input_dir=cache_directory,
    output_dir=str(pathlib.Path(__file__).parent.parent / "results"),
    user_dir="~/.config/automlbenchmark",
    root_dir=str(pathlib.Path(__file__).parent.parent),
)
