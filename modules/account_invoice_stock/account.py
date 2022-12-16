# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


__all__ = ['InvoiceLineStockMove', 'InvoiceLine']


class InvoiceLineStockMove(ModelSQL):
    'Invoice Line - Stock Move'
    __name__ = 'account.invoice.line-stock.move'

    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        required=True, select=True, ondelete='CASCADE')
    stock_move = fields.Many2One('stock.move', 'Stock Move', required=True,
        select=True, ondelete='CASCADE')


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'
    stock_moves = fields.Many2Many('account.invoice.line-stock.move',
        'invoice_line', 'stock_move', 'Stock Moves',
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])

    @property
    def moved_quantity(self):
        'The quantity from linked stock moves in line unit'
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = 0
        for stock_move in self.stock_moves:
            quantity += Uom.compute_qty(stock_move.uom, stock_move.quantity,
                self.unit)
        return quantity

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('stock_moves', None)
        return super(InvoiceLine, cls).copy(lines, default=default)
