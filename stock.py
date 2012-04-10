#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import Pool


class Move(ModelSQL, ModelView):
    _name = 'stock.move'
    anglo_saxon_quantity = fields.Float('Anglo-Saxon Quantity',
        digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])

    def __init__(self):
        super(Move, self).__init__()
        self._sql_constraints += [
            ('check_anglo_saxon_quantity',
                'CHECK(quantity >= anglo_saxon_quantity)',
                'Anglo-Saxon quantity can not be greater than quantity!'),
        ]

    def default_anglo_saxon_quantity(self):
        return 0.0

    def _get_anglo_saxon_move(self, moves, quantity):
        '''
        Generator of (move, qty) where move is the move to be consumed and qty
        is the quantity (in the product default uom) to be consumed on this
        move.
        '''
        uom_obj = Pool().get('product.uom')

        consumed_qty = 0.0
        for move in moves:
            qty = uom_obj.compute_qty(move.uom,
                    move.quantity - move.anglo_saxon_quantity,
                    move.product.default_uom, round=False)
            if qty <= 0.0:
                continue
            if qty > quantity - consumed_qty:
                qty = quantity - consumed_qty
            if consumed_qty >= quantity:
                break
            yield (move, qty)

    def update_anglo_saxon_quantity_product_cost(self, product, moves,
            quantity, uom, type_):
        '''
        Return the cost for quantity based on lines.
        Update anglo_saxon_quantity on the concerned moves.
        '''
        uom_obj = Pool().get('product.uom')

        for move in moves:
            assert move.product == product, 'wrong product'
        assert type_.startswith('in_') or type_.startswith('out_'), 'wrong type'

        total_qty = uom_obj.compute_qty(uom, quantity, product.default_uom,
                round=False)

        cost = Decimal('0.0')
        consumed_qty = 0.0
        for move, move_qty in self._get_anglo_saxon_move(moves, total_qty):
            consumed_qty += move_qty

            if type_.startswith('in_'):
                move_cost_price = uom_obj.compute_price(move.uom,
                        move.unit_price, move.product.default_uom)
            else:
                move_cost_price = move.cost_price
            cost += move_cost_price * Decimal(str(move_qty))

            self.write(move.id, {
                'anglo_saxon_quantity': ((move.anglo_saxon_quantity or 0.0)
                    + move_qty),
                })

        if consumed_qty < total_qty:
            qty = total_qty - consumed_qty
            consumed_qty += qty
            cost += product.cost_price * Decimal(str(qty))
        return cost

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('anglo_saxon_quantity',
            self.default_anglo_saxon_quantity())
        return super(Move, self).copy(ids, default=default)

Move()
