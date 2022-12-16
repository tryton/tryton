# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields, Check
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond import backend

__all__ = ['Move']


def _get_field(type_):
    if type_.startswith('in_'):
        return 'in_anglo_saxon_quantity'
    else:
        return 'out_anglo_saxon_quantity'


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'
    in_anglo_saxon_quantity = fields.Float('Input Anglo-Saxon Quantity',
        required=True)
    out_anglo_saxon_quantity = fields.Float('Output Anglo-Saxon Quantity',
        required=True)

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._allow_modify_closed_period.update(['in_anglo_saxon_quantity',
                'out_anglo_saxon_quantity'])

        t = cls.__table__()
        cls._sql_constraints += [
            ('check_in_anglo_saxon_quantity',
                Check(t, t.quantity >= t.in_anglo_saxon_quantity),
                'Anglo-Saxon quantity can not be greater than quantity.'),
            ('check_out_anglo_saxon_quantity',
                Check(t, t.quantity >= t.out_anglo_saxon_quantity),
                'Anglo-Saxon quantity can not be greater than quantity.'),
            ]

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        TableHandler = backend.get('TableHandler')

        super(Move, cls).__register__(module_name)
        table = TableHandler(cls, module_name)

        # Migration from 2.8: split anglo_saxon_quantity
        if table.column_exist('anglo_saxon_quantity'):
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET in_anglo_saxon_quantity = anglo_saxon_quantity, '
                'out_anglo_saxon_quantity = anglo_saxon_quantity')
            table.drop_constraint('check_anglo_saxon_quantity')
            table.drop_column('anglo_saxon_quantity')

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
        lines = super(Move, self)._get_account_stock_move_lines(type_)
        if (type_.endswith('supplier')
                and self.product.cost_price_method == 'fixed'):
            cost_price = Uom.compute_price(self.product.default_uom,
                self.cost_price, self.uom)
            with Transaction().set_context(date=self.effective_date):
                unit_price = Currency.compute(self.currency, self.unit_price,
                    self.company.currency, round=False)
            amount = self.company.currency.round(
                Decimal(str(self.quantity)) * (unit_price - cost_price))
            if self.company.currency.is_zero(amount):
                return lines
            account = self.product.account_stock_supplier_used
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
            qty = Uom.compute_qty(move.uom,
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
                cost_price = Uom.compute_price(move.uom,
                        unit_price, move.product.default_uom)
            else:
                cost_price = move.cost_price

            yield (move, qty, cost_price)
            consumed_qty += qty

    @classmethod
    def update_anglo_saxon_quantity_product_cost(cls, product, moves,
            quantity, uom, type_):
        '''
        Return the cost for quantity based on lines.
        Update anglo_saxon_quantity on the concerned moves.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')

        for move in moves:
            assert move.product == product, 'wrong product'
        assert type_.startswith('in_') or type_.startswith('out_'), \
            'wrong type'

        total_qty = Uom.compute_qty(uom, quantity, product.default_uom,
                round=False)

        as_qty_field = _get_field(type_)
        cost = Decimal('0.0')
        consumed_qty = 0.0
        for move, move_qty, move_cost_price in cls._get_anglo_saxon_move(
                moves, total_qty, type_):
            consumed_qty += move_qty

            cost += move_cost_price * Decimal(str(move_qty))

            move_qty = Uom.compute_qty(
                product.default_uom, move_qty, move.uom, round=False)

            # Avoid float rounding issue but allow only rounding precision lost
            new_qty = (getattr(move, as_qty_field) or 0.0) + move_qty
            assert move.uom.round(new_qty) <= move.quantity
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
        default = default.copy()
        for prefix in ('in_', 'out_'):
            default.setdefault(prefix + 'anglo_saxon_quantity',
                getattr(cls, 'default_%sanglo_saxon_quantity' % prefix)())
        return super(Move, cls).copy(moves, default=default)
