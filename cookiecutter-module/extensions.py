import io
import os
import re

from jinja2.ext import Extension


def read(fname):
    return io.open(
        os.path.join(os.path.dirname(__file__), fname),
        'r', encoding='utf-8').read()


def get_version():
    init = read(os.path.join(
            os.path.dirname(__file__), '../trytond/trytond/__init__.py'))
    version = re.search('__version__ = "([0-9.]*)"', init).group(1)
    return '.'.join(version.split('.')[:2] + ['0'])


class Version(Extension):
    def __init__(self, environment):
        super().__init__(environment)
        environment.globals.update(version=get_version())
