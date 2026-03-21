#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import glob
import os.path
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        compile_rng(self.build_config.root)


def compile_rng(root: str) -> None:
    for path in glob.glob('**/*.rnc', root_dir=root, recursive=True):
        path = Path(path)
        subprocess.run(['rnc2rng', path, path.with_suffix('.rng')], cwd=root)


if __name__ == '__main__':
    compile_rng(os.path.dirname(__file__))
