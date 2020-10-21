# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import Workflow, ModelView, fields, Check
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Move']


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    fifo_quantity = fields.Float('FIFO Quantity')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._allow_modify_closed_period.add('fifo_quantity')

        t = cls.__table__()
        cls._sql_constraints += [
            ('check_fifo_quantity_out',
                Check(t, t.quantity >= t.fifo_quantity),
                'FIFO quantity can not be greater than quantity.'),
            ]
        cls._error_messages.update({
                'del_move_fifo': ('You can not delete move "%s" that is used '
                    'for FIFO cost price.'),
                })

    @staticmethod
    def default_fifo_quantity():
        return 0.0

    def _update_fifo_out_product_cost_price(self):
        '''
        Update the product cost price of the given product on the move. Update
        fifo_quantity on the concerned incomming moves. Return the
        cost price for outputing the given product and quantity.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        total_qty = Uom.compute_qty(self.uom, self.quantity,
            self.product.default_uom, round=False)

        fifo_moves = self.product.get_fifo_move(total_qty)

        cost_price = Decimal("0.0")
        consumed_qty = 0.0
        to_save = []
        for move, move_qty in fifo_moves:
            consumed_qty += move_qty
            if move.from_location.type in {'supplier', 'production'}:
                with Transaction().set_context(date=move.effective_date):
                    move_unit_price = Currency.compute(
                        move.currency, move.unit_price,
                        self.company.currency, round=False)
                move_unit_price = Uom.compute_price(
                    move.uom, move_unit_price, move.product.default_uom)
            else:
                move_unit_price = move.cost_price or 0
            cost_price += move_unit_price * Decimal(str(move_qty))

            move_qty = Uom.compute_qty(self.product.default_uom, move_qty,
                    move.uom, round=False)
            move.fifo_quantity = (move.fifo_quantity or 0.0) + move_qty
            # Due to float, the fifo quantity result can exceed the quantity.
            assert move.quantity >= move.fifo_quantity - move.uom.rounding
            move.fifo_quantity = min(move.fifo_quantity, move.quantity)
            to_save.append(move)
        if to_save:
            # TODO save in do method when product change
            self.__class__.save(to_save)

        if consumed_qty:
            cost_price = cost_price / Decimal(str(consumed_qty))
        else:
            cost_price = self.product.get_multivalue(
                'cost_price', **self._cost_price_pattern)

        # Compute average cost price
        unit_price = self.unit_price
        self.unit_price = Uom.compute_price(
            self.product.default_uom, cost_price, self.uom)
        average_cost_price = self._compute_product_cost_price('out')
        self.unit_price = unit_price

        if cost_price:
            digits = self.__class__.cost_price.digits
            cost_price = cost_price.quantize(
                Decimal(str(10.0 ** -digits[1])))
        else:
            cost_price = average_cost_price
        return cost_price, average_cost_price

    def _do(self):
        cost_price = super(Move, self)._do()
        if (self.from_location.type in ('supplier', 'production')
                and self.to_location.type == 'storage'
                and self.product.cost_price_method == 'fifo'):
            cost_price = self._compute_product_cost_price('in')
        elif (self.to_location.type == 'supplier'
                and self.from_location.type == 'storage'
                and self.product.cost_price_method == 'fifo'):
            cost_price = self._compute_product_cost_price('out')
        elif (self.from_location.type == 'storage'
                and self.to_location.type != 'storage'
                and self.product.cost_price_method == 'fifo'):
            fifo_cost_price, cost_price = (
                self._update_fifo_out_product_cost_price())
            if self.cost_price is None:
                self.cost_price = fifo_cost_price
        return cost_price

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, moves):
        pass

    @classmethod
    def delete(cls, moves):
        fifo_moves = cls.search([
                ('id', 'in', [m.id for m in moves]),
                ('fifo_quantity', '!=', 0.0),
                ])
        if fifo_moves:
            cls.raise_user_error('del_move_fifo', (fifo_moves[0].rec_name,))
        super(Move, cls).delete(moves)

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('fifo_quantity', cls.default_fifo_quantity())
        return super().copy(moves, default=default)
