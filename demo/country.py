# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.country.scripts.import_countries import do_import
except ImportError:
    def do_import(*args, **kwargs):
        pass

__all__ = [do_import]
