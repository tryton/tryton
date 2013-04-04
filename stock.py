#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from operator import itemgetter

from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval, Bool
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['ShipmentIn', 'Move']
__metaclass__ = PoolMeta


class ShipmentIn:
    __name__ = 'stock.shipment.in'
    carrier = fields.Many2One('carrier', 'Carrier', states={
            'readonly': Eval('state') != 'draft',
            }, on_change=['carrier', 'incoming_moves'],
        depends=['state'])
    cost_currency = fields.Many2One('currency.currency', 'Cost Currency',
        states={
            'required': Bool(Eval('cost')),
            'readonly': ~Eval('state').in_(['draft', 'assigned', 'packed']),
            }, depends=['cost', 'state'])
    cost_currency_digits = fields.Function(fields.Integer(
            'Cost Currency Digits', on_change_with=['currency']),
        'on_change_with_cost_currency_digits')
    cost = fields.Numeric('Cost', digits=(16, Eval('cost_currency_digits', 2)),
        states={
            'readonly': ~Eval('state').in_(['draft', 'assigned', 'packed']),
            }, depends=['carrier', 'state', 'cost_currency_digits'])

    @classmethod
    def __setup__(cls):
        super(ShipmentIn, cls).__setup__()
        if not cls.incoming_moves.on_change:
            cls.incoming_moves.on_change = []
        for fname in ('carrier', 'incoming_moves'):
            if fname not in cls.incoming_moves.on_change:
                cls.incoming_moves.on_change.append(fname)
        for fname in cls.incoming_moves.on_change:
            if fname not in cls.carrier.on_change:
                cls.carrier.on_change.append(fname)

    def on_change_with_cost_currency_digits(self, name=None):
        if self.cost_currency:
            return self.cost_currency.digits
        return 2

    def _get_carrier_context(self):
        return {}

    def on_change_carrier(self):
        return self.on_change_incoming_moves()

    def on_change_incoming_moves(self):
        Currency = Pool().get('currency.currency')

        try:
            result = super(ShipmentIn, self).on_change_incoming_moves()
        except AttributeError:
            result = {}
        if not self.carrier:
            return result
        with Transaction().set_context(self._get_carrier_context()):
            cost, currency_id = self.carrier.get_purchase_price()
        result['cost'] = cost
        result['cost_currency'] = currency_id
        if currency_id:
            currency = Currency(currency_id)
            result['cost_currency_digits'] = currency.digits
        else:
            result['cost_currency_digits'] = 2
        return result

    def allocate_cost_by_value(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Move = pool.get('stock.move')

        if not self.cost:
            return

        cost = Currency.compute(self.cost_currency, self.cost,
            self.company.currency, round=False)
        moves = [m for m in self.incoming_moves
            if m.state not in ('done', 'cancel')]

        sum_value = 0
        unit_prices = {}
        for move in moves:
            unit_price = Currency.compute(move.currency, move.unit_price,
                self.company.currency, round=False)
            unit_prices[move.id] = unit_price
            sum_value += unit_price * Decimal(str(move.quantity))

        costs = []
        digit = Move.unit_price.digits[1]
        exp = Decimal(str(10.0 ** -digit))
        difference = cost
        for move in moves:
            quantity = Decimal(str(move.quantity))
            move_cost = cost * quantity * unit_prices[move.id] / sum_value
            unit_shipment_cost = (move_cost / quantity).quantize(exp,
                rounding=ROUND_DOWN)
            costs.append({
                    'unit_shipment_cost': unit_shipment_cost,
                    'difference': move_cost - (unit_shipment_cost * quantity),
                    'move': move,
                    })
            difference -= unit_shipment_cost * quantity
        costs.sort(key=itemgetter('difference'))
        for cost in costs:
            move = cost['move']
            quantity = Decimal(str(move.quantity))
            if exp * quantity < difference:
                cost['unit_shipment_cost'] += exp
                difference -= exp * quantity
            if difference < exp:
                break

        for cost in costs:
            move = cost['move']
            unit_shipment_cost = Currency.compute(
                self.company.currency, cost['unit_shipment_cost'],
                move.currency, round=False)
            unit_shipment_cost = unit_shipment_cost.quantize(
                exp, rounding=ROUND_HALF_EVEN)
            Move.write([move], {
                    'unit_price': move.unit_price + unit_shipment_cost,
                    'unit_shipment_cost': unit_shipment_cost,
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    def receive(cls, shipments):
        Carrier = Pool().get('carrier')
        for shipment in shipments:
            if shipment.carrier:
                allocation_method = \
                    shipment.carrier.carrier_cost_allocation_method
            else:
                allocation_method = \
                    Carrier.default_carrier_cost_allocation_method()
            getattr(shipment, 'allocate_cost_by_%s' % allocation_method)()
        super(ShipmentIn, cls).receive(shipments)


class Move:
    __name__ = 'stock.move'
    unit_shipment_cost = fields.Numeric('Unit Shipment Cost', digits=(16, 4),
        readonly=True)

    # Split the shipment cost if account_stock_continental is installed
    def _get_account_stock_move_lines(self, type_):
        pool = Pool()
        AccountMoveLine = pool.get('account.move.line')
        Currency = pool.get('currency.currency')
        move_lines = super(Move, self)._get_account_stock_move_lines(type_)
        if (type_.startswith('in_')
                and self.unit_shipment_cost
                and self.shipment
                and self.shipment.carrier):
            shipment_cost = Currency.compute(self.currency,
                Decimal(str(self.quantity)) * self.unit_shipment_cost,
                self.company.currency)
            shipment_cost_account = \
                self.shipment.carrier.carrier_product.account_expense_used
            account = self.product.account_stock_supplier_used
            for move_line in move_lines:
                if move_line.account == account:
                    move_line.credit -= shipment_cost
                    shipment_cost_line = AccountMoveLine(
                        debit=Decimal('0'),
                        credit=shipment_cost,
                        account=shipment_cost_account,
                        )
                    move_lines.append(shipment_cost_line)
                    break
            else:
                raise AssertionError('missing account_stock_supplier')
        return move_lines

    # Remove shipment cost if account_stock_anglo_saxon is installed
    @classmethod
    def _get_anglo_saxon_move(cls, moves, quantity, type_):
        pool = Pool()
        Currency = pool.get('currency.currency')
        for move, qty, cost_price in super(Move, cls)._get_anglo_saxon_move(
                moves, quantity, type_):
            if (type_.startswith('in_')
                    and move.unit_shipment_cost):
                shipment_cost = Currency.compute(move.currency,
                    move.unit_shipment_cost, move.company.currency)
                cost_price -= shipment_cost
            yield move, qty, cost_price
