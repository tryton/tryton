# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.i18n import gettext
from trytond.model import Check, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


def _get_field(type_):
    if type_.startswith('in_'):
        return 'in_anglo_saxon_quantity'
    else:
        return 'out_anglo_saxon_quantity'


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    in_anglo_saxon_quantity = fields.Float(
        "Input Anglo-Saxon Quantity", required=True,
        domain=[
            ('in_anglo_saxon_quantity', '<=', Eval('quantity', 0)),
            ])
    out_anglo_saxon_quantity = fields.Float(
        "Output Anglo-Saxon Quantity", required=True,
        domain=[
            ('out_anglo_saxon_quantity', '<=', Eval('quantity', 0)),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._allow_modify_closed_period.update(['in_anglo_saxon_quantity',
                'out_anglo_saxon_quantity'])

        t = cls.__table__()
        cls._sql_constraints += [
            ('check_in_anglo_saxon_quantity',
                Check(t, t.quantity >= t.in_anglo_saxon_quantity),
                'account_stock_anglo_saxon.msg_move_quantity_greater'),
            ('check_out_anglo_saxon_quantity',
                Check(t, t.quantity >= t.out_anglo_saxon_quantity),
                'account_stock_anglo_saxon.msg_move_quantity_greater'),
            ]

    @staticmethod
    def default_in_anglo_saxon_quantity():
        return 0.0

    @staticmethod
    def default_out_anglo_saxon_quantity():
        return 0.0

    def _get_account_stock_move_lines(self, type_):
        pool = Pool()
        Uom = pool.get('product.uom')
        AccountMoveLine = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        lines = super()._get_account_stock_move_lines(type_)
        cost_price_method = self.product.get_multivalue(
            'cost_price_method', **self._cost_price_pattern)
        if type_.endswith('supplier') and cost_price_method == 'fixed':
            cost_price = Uom.compute_price(
                self.product.default_uom, self.cost_price, self.unit)
            with Transaction().set_context(date=self.effective_date):
                unit_price = Currency.compute(self.currency, self.unit_price,
                    self.company.currency, round=False)
            amount = self.company.currency.round(
                Decimal(str(self.quantity)) * (unit_price - cost_price))
            if self.company.currency.is_zero(amount):
                return lines
            account = self.product.account_stock_in_used
            for move_line in lines:
                if move_line.account == account:
                    break
            else:
                return lines
            if type_.startswith('in_'):
                move_line.credit += amount
                debit = amount
                credit = Decimal(0)
            else:
                move_line.debit += amount
                debit = Decimal(0)
                credit = amount
            if amount < Decimal(0):
                debit, credit = -credit, -debit
            move_line = AccountMoveLine(
                debit=debit,
                credit=credit,
                account=self.product.account_expense_used,
                )
            lines.append(move_line)
        return lines

    @classmethod
    def _get_anglo_saxon_move(cls, moves, quantity, type_):
        '''
        Generator of (move, qty, cost_price) where move is the move to be
        consumed, qty is the quantity (in the product default uom) to be
        consumed on this move and cost_price is in the company currency.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        as_qty_field = _get_field(type_)

        consumed_qty = 0.0
        for move in moves:
            qty = Uom.compute_qty(
                move.unit,
                move.quantity - getattr(move, as_qty_field),
                move.product.default_uom, round=False)
            if qty <= 0.0:
                continue
            if qty > quantity - consumed_qty:
                qty = quantity - consumed_qty
            if consumed_qty >= quantity:
                break

            if type_.endswith('supplier'):
                with Transaction().set_context(date=move.effective_date):
                    unit_price = Currency.compute(move.currency,
                        move.unit_price, move.company.currency, round=False)
                cost_price = Uom.compute_price(
                    move.unit, unit_price, move.product.default_uom)
            else:
                cost_price = move.cost_price

            yield (move, qty, cost_price)
            consumed_qty += qty

    @classmethod
    def update_anglo_saxon_quantity_product_cost(cls, product, moves,
            quantity, unit, type_):
        '''
        Return the cost for quantity based on lines.
        Update anglo_saxon_quantity on the concerned moves.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')

        assert all(m.product == product for m in moves), 'wrong product'
        assert type_.startswith('in_') or type_.startswith('out_'), \
            'wrong type'

        total_qty = Uom.compute_qty(
            unit, quantity, product.default_uom, round=False)

        as_qty_field = _get_field(type_)
        cost = Decimal(0)
        consumed_qty = 0.0
        for move, move_qty, move_cost_price in cls._get_anglo_saxon_move(
                moves, total_qty, type_):
            consumed_qty += move_qty

            cost += move_cost_price * Decimal(str(move_qty))

            move_qty = Uom.compute_qty(
                product.default_uom, move_qty, move.unit, round=False)

            # Avoid float rounding issue but allow only rounding precision lost
            new_qty = (getattr(move, as_qty_field) or 0.0) + move_qty
            assert move.unit.round(new_qty) <= move.quantity
            new_qty = min(new_qty, move.quantity)
            cls.write([move], {
                    as_qty_field: new_qty,
                    })

        if consumed_qty < total_qty:
            qty = total_qty - consumed_qty
            consumed_qty += qty
            cost += product.cost_price * Decimal(str(qty))
        return cost

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        for prefix in ('in_', 'out_'):
            default.setdefault(prefix + 'anglo_saxon_quantity',
                getattr(cls, 'default_%sanglo_saxon_quantity' % prefix)())
        return super().copy(moves, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        for move in moves:
            if move.in_anglo_saxon_quantity or move.out_anglo_saxon_quantity:
                raise AccessError(
                    gettext('account_stock_anglo_saxon'
                        '.msg_move_cancel_anglo_saxon',
                        move=move.rec_name))
        super().cancel(moves)

    @classmethod
    def check_modification(cls, mode, moves, values=None, external=False):
        super().check_modification(
            mode, moves, values=values, external=external)
        if mode == 'delete':
            for move in moves:
                if (move.in_anglo_saxon_quantity
                        or move.out_anglo_saxon_quantity):
                    raise AccessError(gettext(
                            'account_stock_anglo_saxon'
                            '.msg_move_delete_anglo_saxon',
                            move=move.rec_name))
