# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import urlparse

from trytond.config import config

__all__ = ['name', 'get']


def name():
    return urlparse.urlparse(config.get('database', 'uri', default='')).scheme


def get(prop):
    db_type = name()
    modname = 'trytond.backend.%s' % db_type
    __import__(modname)
    module = sys.modules[modname]
    return getattr(module, prop)
