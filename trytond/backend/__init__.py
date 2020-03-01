# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import importlib
import urllib.parse
try:
    import pkg_resources
except ImportError:
    pkg_resources = None

from trytond.config import config

__all__ = [
    'name', 'Database', 'DatabaseIntegrityError',
    'DatabaseOperationalError', 'TableHandler']


name = urllib.parse.urlparse(config.get('database', 'uri', default='')).scheme

_modname = 'trytond.backend.%s' % name
try:
    _module = importlib.import_module(_modname)
except ImportError:
    if not pkg_resources:
        raise
    for ep in pkg_resources.iter_entry_points('trytond.backend', name):
        try:
            _module = ep.load()
            break
        except ImportError:
            continue
    else:
        raise

Database = _module.Database
DatabaseIntegrityError = _module.DatabaseIntegrityError
DatabaseOperationalError = _module.DatabaseOperationalError
TableHandler = _module.TableHandler
