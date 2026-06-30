# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import importlib
import urllib.parse
from importlib.metadata import entry_points

import trytond.config as config
from trytond.tools import resolve

__all__ = [
    'name', 'Database', 'TableHandler',
    'DatabaseIntegrityError', 'DatabaseDataError', 'DatabaseOperationalError',
    'DatabaseTimeoutError', 'MAX_QUERY_PARAMS',
    'dict_row', 'namedtuple_row', 'scalar_row']


name = urllib.parse.urlparse(config.get('database', 'uri', default='')).scheme

_modname = 'trytond.backend.%s' % name
try:
    _module = importlib.import_module(_modname)
except ImportError:
    for ep in entry_points().select(group='trytond.backend', name=name):
        try:
            _module = ep.load()
            break
        except ImportError:
            continue
    else:
        raise


_database_mixins = []
for mixin in config.get(
        'database', 'database_mixins', default='').strip().splitlines():
    _database_mixins.append(resolve(mixin))
_table_handler_mixins = []
for mixin in config.get(
        'database', 'table_handler_mixins', default='').strip().splitlines():
    _table_handler_mixins.append(resolve(mixin))


class Database(*_database_mixins, _module.Database):
    pass


class TableHandler(*_table_handler_mixins, _module.TableHandler):
    pass


DatabaseIntegrityError = _module.DatabaseIntegrityError
DatabaseDataError = _module.DatabaseDataError
DatabaseOperationalError = _module.DatabaseOperationalError
DatabaseTimeoutError = _module.DatabaseTimeoutError
MAX_QUERY_PARAMS = _module.MAX_QUERY_PARAMS
dict_row = _module.dict_row
namedtuple_row = _module.namedtuple_row
scalar_row = _module.scalar_row
