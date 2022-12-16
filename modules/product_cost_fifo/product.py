# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Template', 'Product']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        new_sel = ('fifo', 'FIFO')
        if new_sel not in cls.cost_price_method.selection:
            cls.cost_price_method.selection.append(new_sel)

    def get_fifo_move(self, quantity=0.0):
        '''
        Return a list of (move, qty) where move is the move to be
        consumed and qty is the quantity (in the product default uom)
        to be consumed on this move. The list contains the "first in"
        moves for the given quantity.
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        Location = pool.get('stock.location')
        Template = pool.get('product.template')

        locations = Location.search([
            ('type', '=', 'storage'),
            ])
        stock_date_end = datetime.date.today()
        location_ids = [l.id for l in locations]
        with Transaction().set_context(locations=location_ids,
                stock_date_end=stock_date_end):
            template = Template(self.id)
        offset = 0
        limit = Transaction().database.IN_MAX
        avail_qty = template.quantity
        fifo_moves = []

        while avail_qty > 0.0:
            moves = Move.search([
                ('product.template.id', '=', template.id),
                ('state', '=', 'done'),
                ('from_location.type', '=', 'supplier'),
                ], offset=offset, limit=limit,
                order=[('effective_date', 'DESC'), ('id', 'DESC')])
            if not moves:
                break
            offset += limit

            for move in moves:
                qty = Uom.compute_qty(move.uom,
                        move.quantity - move.fifo_quantity,
                        template.default_uom, round=False)
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


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    def recompute_cost_price_fifo(self):
        return self.recompute_cost_price_average()
