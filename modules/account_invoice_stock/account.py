# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')
        super().post(invoices)
        moves = sum((l.stock_moves for i in invoices for l in i.lines), ())
        if moves:
            Move.__queue__.update_unit_price(moves)


class InvoiceLineStockMove(ModelSQL):
    'Invoice Line - Stock Move'
    __name__ = 'account.invoice.line-stock.move'

    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        required=True, select=True, ondelete='CASCADE')
    stock_move = fields.Many2One('stock.move', 'Stock Move', required=True,
        select=True, ondelete='CASCADE')


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    stock_moves = fields.Many2Many(
        'account.invoice.line-stock.move', 'invoice_line', 'stock_move',
        "Stock Moves",
        domain=[
            ('product.default_uom_category',
                '=', Eval('product_uom_category', -1)),
            If((Eval('_parent_invoice', {}).get('type') == 'out')
                | (Eval('invoice_type') == 'out'),
                ['OR',
                    ('to_location.type', '=', 'customer'),
                    ('from_location.type', '=', 'customer'),
                    ],
                ['OR',
                    ('from_location.type', '=', 'supplier'),
                    ('to_location.type', '=', 'supplier'),
                    ]),
            ],
        states={
            'invisible': (
                (Eval('type') != 'line')
                | ~Eval('product')),
            },
        depends=['type', 'product_uom_category', 'invoice', 'invoice_type'])

    @property
    def moved_quantity(self):
        'The quantity from linked stock moves in line unit'
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = 0
        for stock_move in self.stock_moves:
            if stock_move.state != 'cancelled':
                quantity += Uom.compute_qty(
                    stock_move.uom, stock_move.quantity, self.unit)
        return quantity

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        if not Transaction().context.get('_account_invoice_correction'):
            default.setdefault('stock_moves', None)
        return super(InvoiceLine, cls).copy(lines, default=default)

    def _credit(self):
        line = super()._credit()
        line.stock_moves = self.stock_moves
        return line
