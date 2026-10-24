# Portions of this file are adapted from OpenML AutoML Benchmark
# (https://github.com/openml/automlbenchmark), MIT License, Copyright (c) 2018 OpenML.
# Reference commit: dfe8d21871e2dec2b7cab6c9fbfe3575ce4dadc6 (2025-04-19).
# See THIRD_PARTY_LICENSES/AMLB-LICENSE.txt and NOTICE.md for details.

from enum import Enum, auto

from .file import FileLoader
from .openml import OpenmlLoader


class DataSourceType(Enum):
    openml_task = auto()
    openml_dataset = auto()
    file = auto()


class DataLoader:
    def __init__(self, config):
        self.openml_loader = OpenmlLoader(
            api_key=config.openml.apikey, cache_dir=config.input_dir
        )
        self.file_loader = FileLoader(cache_dir=config.input_dir)

    def load(self, source: DataSourceType, *args, **kwargs):
        if source == DataSourceType.openml_task:
            return self.openml_loader.load(*args, **kwargs)
        elif source == DataSourceType.file:
            return self.file_loader.load(*args, **kwargs)
        else:
            raise NotImplementedError(f"data source {source} is not supported yet")


__all__ = ["DataLoader", "DataSourceType"]
