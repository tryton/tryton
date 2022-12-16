#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from operator import itemgetter

from trytond.model import Model, ModelView, Workflow, fields
from trytond.pyson import Eval, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction


class ShipmentIn(Model):
    _name = 'stock.shipment.in'

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
        'get_cost_currency_digits')
    cost = fields.Numeric('Cost', digits=(16, Eval('cost_currency_digits', 2)),
        states={
            'readonly': ~Eval('state').in_(['draft', 'assigned', 'packed']),
            }, depends=['carrier', 'state', 'cost_currency_digits'])

    def __init__(self):
        super(ShipmentIn, self).__init__()
        self.incoming_moves = copy.copy(self.incoming_moves)
        if not self.incoming_moves.on_change:
            self.incoming_moves.on_change = []
        else:
            self.incoming_moves.on_change = copy.copy(
                self.incoming_moves.on_change)
        for fname in ('carrier', 'incoming_moves'):
            if fname not in self.incoming_moves.on_change:
                self.incoming_moves.on_change.append(fname)
        self._rpc.setdefault('on_change_incoming_moves', False)
        self.carrier = copy.copy(self.carrier)
        self.carrier.on_change = copy.copy(self.carrier.on_change)
        for fname in self.incoming_moves.on_change:
            if fname not in self.carrier.on_change:
                self.carrier.on_change.append(fname)
        self._reset_columns()

    def on_change_with_cost_currency_digits(self, values):
        currency_obj = Pool().get('currency.currency')
        if values.get('cost_currency'):
            currency = currency_obj.browse(values['cost_currency'])
            return currency.digits
        return 2

    def get_cost_currency_digits(self, ids, name):
        '''
        Return the number of digits of the cost currency
        '''
        result = {}
        for shipment in self.browse(ids):
            if shipment.cost_currency:
                result[shipment.id] = shipment.cost_currency.digits
            else:
                result[shipment.id] = 2
        return result

    def _get_carrier_context(self, values):
        return {}

    def on_change_carrier(self, values):
        return self.on_change_incoming_moves(values)

    def on_change_incoming_moves(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        currency_obj = pool.get('currency.currency')

        try:
            result = super(ShipmentIn, self).on_change_incoming_moves(values)
        except AttributeError:
            result = {}
        if not values.get('carrier'):
            return result
        carrier = carrier_obj.browse(values['carrier'])
        with Transaction().set_context(
                self._get_carrier_context(values)):
            cost, currency_id = carrier_obj.get_purchase_price(carrier)
        result['cost'] = cost
        result['cost_currency'] = currency_id
        if currency_id:
            currency = currency_obj.browse(currency_id)
            result['cost_currency_digits'] = currency.digits
        else:
            result['cost_currency_digits'] = 2
        return result

    def allocate_cost_by_value(self, shipment):
        currency_obj = Pool().get('currency.currency')
        move_obj = Pool().get('stock.move')

        if not shipment.cost:
            return

        cost = currency_obj.compute(shipment.cost_currency, shipment.cost,
            shipment.company.currency, round=False)
        moves = [m for m in shipment.incoming_moves
            if m.state not in ('done', 'cancel')]

        sum_value = 0
        unit_prices = {}
        for move in moves:
            unit_price = currency_obj.compute(move.currency, move.unit_price,
                shipment.company.currency, round=False)
            unit_prices[move.id] = unit_price
            sum_value += unit_price * Decimal(str(move.quantity))

        costs = []
        digit = move_obj.unit_price.digits[1]
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
            unit_shipment_cost = currency_obj.compute(
                shipment.company.currency, cost['unit_shipment_cost'],
                move.currency, round=False)
            unit_shipment_cost = unit_shipment_cost.quantize(
                exp, rounding=ROUND_HALF_EVEN)
            move_obj.write(move.id, {
                    'unit_price': move.unit_price + unit_shipment_cost,
                    'unit_shipment_cost': unit_shipment_cost,
                    })

    @ModelView.button
    @Workflow.transition('received')
    def receive(self, ids):
        carrier_obj = Pool().get('carrier')
        for shipment in self.browse(ids):
            if shipment.carrier:
                allocation_method = \
                    shipment.carrier.carrier_cost_allocation_method
            else:
                allocation_method = \
                    carrier_obj.default_carrier_cost_allocation_method()
            getattr(self, 'allocate_cost_by_%s' % allocation_method)(shipment)
        super(ShipmentIn, self).receive(ids)

ShipmentIn()


class Move(Model):
    _name = 'stock.move'

    unit_shipment_cost = fields.Numeric('Unit Shipment Cost', digits=(16, 4),
        readonly=True)

    # Split the shipment cost if account_stock_continental is installed
    def _get_account_stock_move_lines(self, move, type_):
        currency_obj = Pool().get('currency.currency')
        move_lines = super(Move, self)._get_account_stock_move_lines(move,
            type_)
        if (type_.startswith('in_')
                and move.unit_shipment_cost
                and move.shipment_in
                and move.shipment_in.carrier):
            shipment_cost = currency_obj.compute(move.currency,
                Decimal(str(move.quantity)) * move.unit_shipment_cost,
                move.company.currency)
            shipment_cost_account = \
                move.shipment_in.carrier.carrier_product.account_expense_used
            account_id = move.product.account_stock_supplier_used.id
            for move_line in move_lines:
                if move_line['account'] == account_id:
                    move_line['credit'] -= shipment_cost
                    shipment_cost_line = {
                        'name': move.rec_name,
                        'debit': Decimal('0'),
                        'credit': shipment_cost,
                        'account': shipment_cost_account,
                        }
                    move_lines.append(shipment_cost_line)
                    break
            else:
                raise AssertionError('missing account_stock_supplier')
        return move_lines

Move()
