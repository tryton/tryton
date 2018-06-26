# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import urllib.parse
import os
import imp
try:
    import pkg_resources
except ImportError:
    pkg_resources = None

from trytond.config import config

__all__ = ['name', 'get']


def name():
    return urllib.parse.urlparse(config.get('database', 'uri', default='')).scheme


def get(prop):
    db_type = name()
    modname = 'trytond.backend.%s' % db_type
    if modname not in sys.modules:
        try:
            __import__(modname)
        except ImportError as exception:
            if not pkg_resources:
                raise exception
            try:
                ep, = pkg_resources.iter_entry_points(
                    'trytond.backend', db_type)
            except ValueError:
                raise exception
            mod_path = os.path.join(ep.dist.location,
                *ep.module_name.split('.')[:-1])
            fp, pathname, description = imp.find_module(db_type, [mod_path])
            imp.load_module(modname, fp, pathname, description)
    module = sys.modules[modname]
    return getattr(module, prop)
