# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import importlib
import urllib.parse

try:
    from backports.entry_points_selectable import entry_points
except ImportError:
    from importlib.metadata import entry_points

from trytond.config import config

__all__ = [
    'name', 'Database', 'TableHandler',
    'DatabaseIntegrityError', 'DatabaseDataError', 'DatabaseOperationalError',
    'DatabaseTimeoutError']


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

Database = _module.Database
DatabaseIntegrityError = _module.DatabaseIntegrityError
DatabaseDataError = _module.DatabaseDataError
DatabaseOperationalError = _module.DatabaseOperationalError
DatabaseTimeoutError = _module.DatabaseTimeoutError
TableHandler = _module.TableHandler
