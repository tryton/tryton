#!/usr/bin/env python

import doctest
import glob
import os
from itertools import chain
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))

if __name__ == '__main__':
    parser = doctest.DocTestParser()

    for filename in chain(glob.glob('**/*/tests/*.rst', root_dir=ROOT_DIR)):
        filename = Path(filename)
        with open(filename, 'r') as scenario:
            text = scenario.read()

        with open(filename.with_suffix('.py'), 'w') as file:
            lineno = -1
            for line in parser.parse(text):
                if isinstance(line, doctest.Example):
                    file.write(('#\n' * (line.lineno - lineno - 1))[1:])
                    file.write(line.source)
                    lineno = line.lineno + len(line.source.splitlines()) - 1
                    newline = False
                else:
                    pass
