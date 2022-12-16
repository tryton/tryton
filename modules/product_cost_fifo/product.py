# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Template', 'Product']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        new_sel = ('fifo', 'FIFO')
        if new_sel not in cls.cost_price_method.selection:
            cls.cost_price_method._field.selection.append(new_sel)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def _get_available_fifo_moves(self):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.search([
                ('product', '=', self.id),
                ('state', '=', 'done'),
                self._domain_moves_cost,
                ('fifo_quantity_available', '>', 0),
                ('to_location.type', '=', 'storage'),
                ('from_location.type', '!=', 'storage'),
                ('to_location.type', '=', 'storage'),
                ], order=[('effective_date', 'DESC'), ('id', 'DESC')])

    def _get_fifo_quantity(self):
        pool = Pool()
        Location = pool.get('stock.location')

        locations = Location.search([
            ('type', '=', 'storage'),
            ])
        stock_date_end = datetime.date.today()
        location_ids = [l.id for l in locations]
        with Transaction().set_context(
                locations=location_ids,
                stock_date_end=stock_date_end):
            return self.__class__(self.id).quantity

    def get_fifo_move(self, quantity=0.0):
        '''
        Return a list of (move, qty) where move is the move to be
        consumed and qty is the quantity (in the product default uom)
        to be consumed on this move. The list contains the "first in"
        moves for the given quantity.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')

        avail_qty = self._get_fifo_quantity()
        fifo_moves = []
        moves = self._get_available_fifo_moves()
        for move in moves:
            qty = Uom.compute_qty(move.uom,
                    move.fifo_quantity_available,
                    self.default_uom, round=False)
            avail_qty -= qty

            if avail_qty <= quantity:
                if avail_qty > 0.0:
                    fifo_moves.append(
                        (move, min(qty, quantity - avail_qty)))
                else:
                    fifo_moves.append(
                        (move, min(quantity, qty + avail_qty)))
                    break
        fifo_moves.reverse()
        return fifo_moves

    def recompute_cost_price_fifo(self):
        return self.recompute_cost_price_average()
