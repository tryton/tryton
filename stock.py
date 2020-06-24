# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.product import round_price


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    invoice_lines = fields.Many2Many(
        'account.invoice.line-stock.move', 'stock_move', 'invoice_line',
        "Invoice Lines",
        domain=[
            ('product.default_uom_category',
                '=', Eval('product_uom_category', -1)),
            ('type', '=', 'line'),
            ['OR',
                ('invoice.type', 'in', Eval('invoice_types', [])),
                ('invoice_type', 'in', Eval('invoice_types', [])),
                ],
            ],
        depends=['product_uom_category', 'invoice_types'])
    invoice_types = fields.Function(
        fields.MultiSelection('get_invoice_types', "Invoice Types"),
        'on_change_with_invoice_types')

    @classmethod
    def get_invoice_types(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice.fields_get(['type'])['type']['selection'] + [(None, '')]

    @fields.depends('from_location', 'to_location')
    def on_change_with_invoice_types(self, name=None):
        types = set()
        for location in [self.from_location, self.to_location]:
            if location:
                if location.type == 'customer':
                    types.add('out')
                elif location.type == 'supplier':
                    types.add('in')
        return list(types)

    @property
    def invoiced_quantity(self):
        'The quantity from linked invoice lines in move unit'
        pool = Pool()
        Uom = pool.get('product.uom')
        quantity = 0
        for invoice_line in self.invoice_lines:
            if invoice_line.invoice_state != 'cancelled':
                quantity += Uom.compute_qty(
                    invoice_line.unit, invoice_line.quantity, self.uom)
        return quantity

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        if not Transaction().context.get('_stock_move_split'):
            default.setdefault('invoice_lines', None)
        return super().copy(moves, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        super().do(moves)
        cls.update_unit_price(moves)

    @classmethod
    def update_unit_price(cls, moves):
        for move in moves:
            if move.state == 'done':
                unit_price = move._compute_unit_price()
                if unit_price != move.unit_price:
                    move.unit_price = unit_price
        cls.save(moves)

    def _compute_unit_price(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        Currency = pool.get('currency.currency')
        amount, quantity = 0, 0
        for line in self.invoice_lines:
            if line.invoice and line.invoice.state in {'posted', 'paid'}:
                with Transaction().set_context(date=self.effective_date):
                    amount += Currency.compute(
                        line.invoice.currency, line.amount, self.currency)
                quantity += UoM.compute_qty(
                    line.unit, line.quantity, self.uom)
        if not quantity:
            unit_price = self.unit_price
        else:
            unit_price = round_price(amount / Decimal(str(quantity)))
        return unit_price


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _sync_outgoing_move(self, template=None):
        move = super()._sync_outgoing_move(template=template)
        if template and template.invoice_lines:
            move.invoice_lines = list(template.invoice_lines)
        return move
