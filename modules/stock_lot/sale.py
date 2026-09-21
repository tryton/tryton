# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class POSSaleLine(metaclass=PoolMeta):
    __name__ = 'sale.point.sale.line'

    lot = fields.Many2One(
        'stock.lot', "Lot", ondelete='RESTRICT',
        domain=[
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'readonly': Eval('sale_state') != 'open',
            'required': Eval('lot_required', False),
            })
    lot_required = fields.Function(
        fields.Boolean("Lot Required"),
        'on_change_with_lot_required')

    @fields.depends('product', methods=['from_location', 'to_location'])
    def on_change_with_lot_required(self, name=None):
        if self.product and self.from_location and self.to_location:
            return self.product.lot_is_required(
                self.from_location, self.to_location)

    @fields.depends('product', 'lot')
    def on_change_product(self):
        try:
            super().on_change_product()
        except AttributeError:
            pass
        if self.lot and self.lot.product != self.product:
            self.lot = None

    def get_stock_move(self):
        move = super().get_stock_move()
        if move:
            move.lot = self.lot
        return move
