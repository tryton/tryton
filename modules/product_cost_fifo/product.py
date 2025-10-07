# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from decimal import Decimal

import trytond.config as config
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        new_sel = ('fifo', 'FIFO')
        if new_sel not in cls.cost_price_method.selection:
            cls.cost_price_method._field.selection.append(new_sel)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def _get_available_fifo_moves(self, date=None, offset=0, limit=None):
        pool = Pool()
        Move = pool.get('stock.move')

        domain = [
            ('product', '=', self.id),
            self._domain_moves_cost(),
            ('from_location.type', '!=', 'storage'),
            ('to_location.type', '=', 'storage'),
            ]
        if not date:
            domain.append(('fifo_quantity_available', '>', 0))
        else:
            domain.append(('effective_date', '<=', date))
        return Move.search(
            domain,
            offset=offset, limit=limit,
            order=[('effective_date', 'DESC'), ('id', 'DESC')])

    def get_fifo_move(self, quantity=0.0, date=None):
        '''
        Return a list of (move, qty) where move is the move to be
        consumed and qty is the quantity (in the product default uom)
        to be consumed on this move. The list contains the "first in"
        moves for the given quantity.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')

        avail_qty = self._get_storage_quantity(date=date)
        if date:
            # On recomputation, we must pretend
            # outgoing moves are not yet done.
            avail_qty += quantity
        fifo_moves = []

        size = config.getint('cache', 'record')

        def moves():
            offset, limit = 0, size
            while True:
                moves = self._get_available_fifo_moves(
                    date=date, offset=offset, limit=limit)
                if not moves:
                    break
                for move in moves:
                    yield move
                offset += size

        for move in moves():
            qty = move.fifo_quantity_available if not date else move.quantity
            qty = Uom.compute_qty(
                move.unit, qty, self.default_uom, round=False)
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

    def recompute_cost_price_fifo(self, start=None):
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        Revision = pool.get('product.cost_price.revision')

        domain = [
            ('product', '=', self.id),
            self._domain_moves_cost(),
            ['OR',
                self._domain_in_moves_cost(),
                self._domain_out_moves_cost(),
                ]
            ]
        if start:
            domain.append(('effective_date', '>=', start))
        moves = Move.search(
                domain, order=[('effective_date', 'ASC'), ('id', 'ASC')])

        _in_moves = Move.search([
                ('product', '=', self.id),
                self._domain_moves_cost(),
                self._domain_in_moves_cost(),
                ], order=[])
        _in_moves = set(m.id for m in _in_moves)

        revisions = Revision.get_for_product(self)

        cost_price = Decimal(0)
        quantity = 0
        if start:
            domain.remove(('effective_date', '>=', start))
            domain.append(('effective_date', '<', start))
            domain.append(self._domain_in_moves_cost())
            prev_moves = Move.search(
                domain,
                order=[('effective_date', 'DESC'), ('id', 'DESC')],
                limit=1)
            if prev_moves:
                move, = prev_moves
                cost_price = move.cost_price
                quantity = self._get_storage_quantity(
                    date=start - dt.timedelta(days=1))
                quantity = Decimal(str(quantity))

        def in_move(move):
            return move.id in _in_moves

        def out_move(move):
            return not in_move(move)

        def production_move(move):
            return (
                move.from_location.type == 'production'
                or move.to_location.type == 'production')

        def compute_fifo_cost_price(quantity, date):
            fifo_moves = self.get_fifo_move(float(quantity), date=date)

            cost_price = Decimal(0)
            consumed_qty = 0
            for move, move_qty in fifo_moves:
                consumed_qty += move_qty
                cost_price += move.get_cost_price() * Decimal(str(move_qty))
            if consumed_qty:
                return round_price(cost_price / Decimal(str(consumed_qty)))

        # For each day, process the incoming moves first
        # in order to keep quantity positive where possible
        # We do not re-browse because we expect only small changes
        moves = sorted(moves, key=lambda m: (
                m.effective_date,
                out_move(m) or (in_move(m) and production_move(m)),
                m.id))
        current_moves = []
        current_out_qty = 0
        current_cost_price = cost_price
        qty_production = 0
        for move in moves:
            if (current_moves
                    and current_moves[-1].effective_date
                    != move.effective_date):
                Move.write([
                        m for m in filter(in_move, current_moves)
                        if m.cost_price != current_cost_price],
                    dict(cost_price=current_cost_price))

                out_moves = list(filter(out_move, current_moves))
                if out_moves:
                    fifo_cost_price = compute_fifo_cost_price(
                        current_out_qty, current_moves[-1].effective_date)
                    if fifo_cost_price is None:
                        fifo_cost_price = current_cost_price
                    if quantity > 0 and quantity + current_out_qty >= 0:
                        cost_price = (
                            ((current_cost_price * (
                                        quantity + current_out_qty))
                                - (fifo_cost_price * current_out_qty))
                            / quantity)
                    else:
                        cost_price = current_cost_price
                    current_cost_price = round_price(cost_price)
                    Move.write([
                            m for m in out_moves
                            if m.cost_price != fifo_cost_price
                            or m.product_cost_price != current_cost_price],
                        dict(
                            cost_price=fifo_cost_price,
                            product_cost_price=current_cost_price))
                current_moves.clear()
                current_out_qty = 0
                qty_production = 0
            current_moves.append(move)

            cost_price = Revision.apply_up_to(
                revisions, cost_price, move.effective_date)
            qty = Uom.compute_qty(move.unit, move.quantity, self.default_uom)
            qty = Decimal(str(qty))
            if out_move(move):
                qty *= -1
            if in_move(move):
                in_qty = qty
                if production_move(move) and qty_production < 0:
                    # Exclude quantity coming back from production
                    in_qty -= min(abs(qty_production), in_qty)
                unit_price = move.get_cost_price(product_cost_price=cost_price)
                if quantity + in_qty > 0 and quantity >= 0:
                    cost_price = (
                        (cost_price * quantity) + (unit_price * in_qty)
                        ) / (quantity + in_qty)
                elif in_qty > 0:
                    cost_price = unit_price
                current_cost_price = round_price(cost_price)
            elif out_move(move):
                current_out_qty += -qty
            quantity += qty
            if production_move(move):
                qty_production += qty

        Move.write([
                m for m in filter(in_move, current_moves)
                if m.cost_price != current_cost_price],
            dict(cost_price=current_cost_price))

        out_moves = list(filter(out_move, current_moves))
        if out_moves:
            fifo_cost_price = compute_fifo_cost_price(
                current_out_qty, current_moves[-1].effective_date)
            if fifo_cost_price is None:
                fifo_cost_price = current_cost_price
            if quantity > 0:
                cost_price = (
                    ((cost_price * (quantity + current_out_qty))
                        - (fifo_cost_price * current_out_qty))
                    / quantity)
            else:
                cost_price = current_cost_price
            current_cost_price = round_price(cost_price)
            Move.write([
                    m for m in out_moves
                    if m.cost_price != fifo_cost_price
                    or m.product_cost_price != current_cost_price],
                dict(
                    cost_price=fifo_cost_price,
                    product_cost_price=current_cost_price))
        for revision in revisions:
            cost_price = revision.get_cost_price(cost_price)
        return cost_price
