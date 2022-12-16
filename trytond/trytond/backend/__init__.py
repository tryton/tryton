# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import importlib
import sys
import urllib.parse
try:
    import pkg_resources
except ImportError:
    pkg_resources = None

from trytond.config import config

__all__ = ['name', 'get']


def name():
    return urllib.parse.urlparse(
        config.get('database', 'uri', default='')).scheme


def get(prop):
    db_type = name()
    modname = 'trytond.backend.%s' % db_type
    try:
        module = importlib.import_module(modname)
    except ImportError:
        if not pkg_resources:
            raise
        for ep in pkg_resources.iter_entry_points(
                'trytond.backend', db_type):
            try:
                sys.modules[modname] = module = ep.load()
                break
            except ImportError:
                continue
        else:
            raise
    return getattr(module, prop)
