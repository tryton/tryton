# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    shipments = fields.Function(fields.Char("Shipments"), 'get_shipments')

    def get_shipments(self, name):
        shipments = {
            m.shipment.rec_name for l in self.lines
            for m in l.stock_moves if m.shipment}
        return ', '.join(sorted(shipments))

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Move = pool.get('stock.move')
        transaction = Transaction()
        context = transaction.context
        super()._post(invoices)
        moves = sum((l.stock_moves for i in invoices for l in i.lines), ())
        if moves:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
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

    warehouse = fields.Function(fields.Many2One(
            'stock.location', "Warehouse"), 'get_warehouse')
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
            })
    shipments = fields.Function(fields.Char("Shipments"), 'get_shipments')
    correction = fields.Boolean(
        "Correction",
        states={
            'invisible': ((Eval('_parent_invoice', {}).get('type') == 'out')
                | (Eval('invoice_type') == 'out')),
            },
        help="Check to correct price of already posted invoice.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude.add('stock_moves')

    @classmethod
    def default_correction(cls):
        return False

    def get_warehouse(self, name):
        if (self.invoice_type == 'out'
                or (self.invoice and self.invoice.type) == 'out'):
            warehouses = set(filter(None, [
                        m.from_location.warehouse for m in self.stock_moves]))
        else:
            warehouses = set(filter(None, [
                        m.to_location.warehouse for m in self.stock_moves]))
        if warehouses:
            return list(warehouses)[0].id

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

    def get_shipments(self, name):
        shipments = {
            m.shipment.rec_name for m in self.stock_moves if m.shipment}
        return ', '.join(sorted(shipments))

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Move = pool.get('stock.move')
        transaction = Transaction()
        context = transaction.context
        super().write(*args)
        lines = sum(args[0:None:2], [])
        moves = sum((l.stock_moves for l in lines), ())
        if moves:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Move.__queue__.update_unit_price(moves)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('correction', False)
        if not Transaction().context.get('_account_invoice_correction'):
            default.setdefault('stock_moves', None)
        return super(InvoiceLine, cls).copy(lines, default=default)

    def _credit(self):
        line = super()._credit()
        line.stock_moves = self.stock_moves
        return line
