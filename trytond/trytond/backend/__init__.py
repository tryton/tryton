#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys

from trytond.config import CONFIG

__all__ = ['get']


def get(name):
    db_type = CONFIG['db_type']
    modname = 'trytond.backend.%s' % db_type
    __import__(modname)
    module = sys.modules[modname]
    return getattr(module, name)
