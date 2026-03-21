#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os.path
from pathlib import Path
from typing import Any

from babel.messages.frontend import CommandLineInterface
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        compile_translations(self.build_config.root)


def compile_translations(root: str) -> None:
    locale = Path(root) / 'tryton/data/locale'
    CommandLineInterface().run([
            'pybabel', '-q', 'compile', '-d', locale, '-D', 'tryton'])


if __name__ == '__main__':
    compile_translations(os.path.dirname(__file__))
