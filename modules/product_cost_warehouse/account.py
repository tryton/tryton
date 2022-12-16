# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.context['warehouse'] = Eval('warehouse', -1)
        cls.product.depends.add('warehouse')
