# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_invoice_line(self):
        with Transaction().set_context(
                taxes=[t.id for t in self.taxes],
                return_=self.quantity < 0):
            return super().get_invoice_line()
