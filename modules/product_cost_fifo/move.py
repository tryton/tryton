# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Literal, operators

from trytond.i18n import gettext
from trytond.model import Check, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    fifo_quantity = fields.Float(
        "FIFO Quantity", required=True,
        domain=[
            ('fifo_quantity', '<=', Eval('quantity', 0)),
            ],
        help="Quantity used by FIFO.")
    fifo_quantity_available = fields.Function(fields.Float(
            "FIFO Quantity Available",
            help="Quantity available for FIFO"),
        'get_fifo_quantity_available')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period.add('fifo_quantity')

        t = cls.__table__()
        cls._sql_constraints += [
            ('check_fifo_quantity',
                Check(t, t.quantity >= t.fifo_quantity),
                'product_cost_fifo.msg_move_fifo_quantity_greater'),
            ]

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)

        # Migration from 6.6: rename check_fifo_quantity_out to
        # check_fifo_quantity
        table_h.drop_constraint('check_fifo_quantity_out')

    @staticmethod
    def default_fifo_quantity():
        return 0.0

    def get_fifo_quantity_available(self, name):
        return self.quantity - (self.fifo_quantity or 0)

    @classmethod
    def domain_fifo_quantity_available(cls, domain, tables):
        table, _ = tables[None]
        name, operator, value = domain
        field = cls.fifo_quantity_available._field
        Operator = fields.SQL_OPERATORS[operator]
        column = (
            cls.quantity.sql_column(table)
            - cls.fifo_quantity.sql_column(table))
        expression = Operator(column, field._domain_value(operator, value))
        if isinstance(expression, operators.In) and not expression.right:
            expression = Literal(False)
        elif isinstance(expression, operators.NotIn) and not expression.right:
            expression = Literal(True)
        expression = field._domain_add_null(
            column, operator, value, expression)
        return expression

    def _update_fifo_out_product_cost_price(self):
        '''
        Update the product cost price of the given product on the move. Update
        fifo_quantity on the concerned incoming moves. Return the
        cost price for outputing the given product and quantity.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')

        total_qty = Uom.compute_qty(
            self.unit, self.quantity, self.product.default_uom, round=False)

        with Transaction().set_context(company=self.company.id):
            fifo_moves = self.product.get_fifo_move(total_qty)

        cost_price = Decimal(0)
        consumed_qty = 0.0
        to_save = []
        for move, move_qty in fifo_moves:
            consumed_qty += move_qty
            cost_price += move.get_cost_price() * Decimal(str(move_qty))

            move_qty = Uom.compute_qty(
                self.product.default_uom, move_qty, move.unit, round=False)
            move.fifo_quantity = (move.fifo_quantity or 0.0) + move_qty
            # Due to float, the fifo quantity result can exceed the quantity.
            assert move.quantity >= move.fifo_quantity - move.unit.rounding
            move.fifo_quantity = min(move.fifo_quantity, move.quantity)
            to_save.append(move)

        if consumed_qty:
            cost_price = cost_price / Decimal(str(consumed_qty))
        else:
            cost_price = self.product.get_multivalue(
                'cost_price', **self._cost_price_pattern)

        # Compute average cost price
        average_cost_price = self._compute_product_cost_price(
            'out', product_cost_price=cost_price)

        if cost_price:
            cost_price = round_price(cost_price)
        else:
            cost_price = average_cost_price
        return cost_price, average_cost_price, to_save

    def _do(self):
        cost_price, to_save = super()._do()
        cost_price_method = self.product.get_multivalue(
            'cost_price_method', **self._cost_price_pattern)
        if (self.from_location.type != 'storage'
                and self.to_location.type == 'storage'
                and cost_price_method == 'fifo'):
            cost_price = self._compute_product_cost_price('in')
        elif (self.to_location.type == 'supplier'
                and self.from_location.type == 'storage'
                and cost_price_method == 'fifo'):
            cost_price = self._compute_product_cost_price('out')
        elif (self.from_location.type == 'storage'
                and self.to_location.type != 'storage'
                and cost_price_method == 'fifo'):
            fifo_cost_price, cost_price, moves = (
                self._update_fifo_out_product_cost_price())
            if self.cost_price_required:
                if self.cost_price is None:
                    self.cost_price = fifo_cost_price
                if self.product_cost_price is None:
                    self.product_cost_price = cost_price
            to_save.extend(moves)
        return cost_price, to_save

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        for move in moves:
            if move.fifo_quantity:
                raise AccessError(
                    gettext('product_cost_fifo.msg_move_cancel_fifo',
                        move=move.rec_name))
        super().cancel(moves)

    @classmethod
    def check_modification(cls, mode, moves, values=None, external=False):
        super().check_modification(
            mode, moves, values=values, external=external)
        if mode == 'delete':
            for move in moves:
                if move.fifo_quantity:
                    raise AccessError(gettext(
                            'product_cost_fifo.msg_move_delete_fifo',
                            move=move.rec_name))

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('fifo_quantity', cls.default_fifo_quantity())
        return super().copy(moves, default=default)
