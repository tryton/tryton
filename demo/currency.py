# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from proteus import Model

try:
    from trytond.modules.currency.scripts.import_currencies import do_import
except ImportError:
    def do_import(*args, **kwargs):
        Currency = Model.get('currency.currency')
        usd = Currency(name="USD", code='USD')
        usd.save()

__all__ = [do_import]
