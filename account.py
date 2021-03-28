# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta, Pool

from .common import IncotermMixin


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    incoterms = fields.Function(fields.Char("Incoterms"), 'get_incoterms')

    def get_incoterms(self, name):
        return '; '.join(set(filter(None,
                    (l.incoterm_name for l in self.lines))))


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def incoterm_name(self):
        pool = Pool()
        try:
            SaleLine = pool.get('sale.line')
        except KeyError:
            SaleLine = None
        try:
            PurchaseLine = pool.get('purchase.line')
        except KeyError:
            PurchaseLine = None
        name = ''
        if self.stock_moves:
            name = ','.join({
                    move.shipment.incoterm_name
                    for move in self.stock_moves
                    if (move.state != 'cancelled'
                        and isinstance(move.shipment, IncotermMixin))})
        elif (SaleLine
                and isinstance(self.origin, SaleLine)
                and isinstance(self.origin.sale, IncotermMixin)):

            name = self.origin.sale.incoterm_name
        elif (PurchaseLine
                and isinstance(self.origin, PurchaseLine)
                and isinstance(self.origin.purchase, IncotermMixin)):
            name = self.origin.purchase.incoterm_name
        return name
