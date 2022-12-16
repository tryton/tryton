# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta


__all__ = ['StockMove']


class StockMove:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'
    invoice_lines = fields.Many2Many('account.invoice.line-stock.move',
        'stock_move', 'invoice_line', 'Invoice Lines')

    @property
    def invoiced_quantity(self):
        'The quantity from linked invoice lines in move unit'
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = 0
        for invoice_line in self.invoice_lines:
            quantity += Uom.compute_qty(invoice_line.unit,
                invoice_line.quantity, self.uom)
        return quantity

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_lines', None)
        return super(StockMove, cls).copy(moves, default=default)
