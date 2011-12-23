#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import copy
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool


class ShipmentOut(ModelWorkflow, ModelSQL, ModelView):
    _name = 'stock.shipment.out'

    carrier = fields.Many2One('carrier', 'Carrier', states={
            'readonly': Eval('state') != 'draft',
            }, on_change=['carrier'],
        depends=['state'])
    cost_currency = fields.Many2One('currency.currency',
            'Cost Currency', states={
            'invisible': ~Eval('carrier'),
            'required': Bool(Eval('carrier')),
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'packed']),
            }, depends=['carrier', 'state'])
    cost_currency_digits = fields.Function(fields.Integer(
        'Cost Currency Digits', on_change_with=['currency']),
        'get_cost_currency_digits')
    cost = fields.Numeric('Cost',
            digits=(16, Eval('cost_currency_digits', 2)), states={
            'invisible': ~Eval('carrier'),
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'packed']),
            }, depends=['carrier', 'state', 'cost_currency_digits'])
    cost_invoice_line = fields.Many2One('account.invoice.line',
            'Cost Invoice Line', readonly=True)

    def __init__(self):
        super(ShipmentOut, self).__init__()
        self._error_messages.update({
            'missing_account_revenue': 'It misses '
                    'an "Account Revenue" on product "%s"!',
            })
        self.inventory_moves = copy.copy(self.inventory_moves)
        if not self.inventory_moves.on_change:
            self.inventory_moves.on_change = []
        else:
            self.inventory_moves.on_change = copy.copy(
                self.inventory_moves.on_change)
        for fname in ('carrier', 'customer', 'inventory_moves'):
            if fname not in self.inventory_moves.on_change:
                self.inventory_moves.on_change.append(fname)
        self._rpc.setdefault('on_change_inventory_moves', False)
        self.carrier = copy.copy(self.carrier)
        self.carrier.on_change = copy.copy(self.carrier.on_change)
        for fname in self.inventory_moves.on_change:
            if fname not in self.carrier.on_change:
                self.carrier.on_change.append(fname)
        self._reset_columns()

    def on_change_with_cost_currency_digits(self, values):
        currency_obj = Pool().get('currency.currency')
        if values.get('currency'):
            currency = currency_obj.browse(values['currency'])
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

    def get_carrier_context(self, shipment, values=None):
        if values is None:
            values = {}
        return self._get_carrier_context(values)

    def on_change_carrier(self, values):
        return self.on_change_inventory_moves(values)

    def on_change_inventory_moves(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        currency_obj = pool.get('currency.currency')

        try:
            result = super(ShipmentOut, self).on_change_inventory_moves(values)
        except AttributeError:
            result = {}
        if not values.get('carrier'):
            return result
        carrier = carrier_obj.browse(values['carrier'])
        with Transaction().set_context(
                self._get_carrier_context(values)):
            cost, currency_id = carrier_obj.get_sale_price(carrier)
        currency = currency_obj.browse(currency_id)
        result['cost'] = cost
        result['cost_currency'] = currency_id
        result['cost_currency_digits'] = currency.digits if currency else 2
        return result

    def _get_cost_tax_rule_pattern(self, shipment):
        'Get tax rule pattern for invoice line'
        return {}

    def get_cost_invoice_line(self, shipment, invoice):
        pool = Pool()
        product_obj = pool.get('product.product')
        tax_rule_obj = pool.get('account.tax.rule')
        currency_obj = pool.get('currency.currency')

        if not shipment.cost:
            return {}
        values = {}
        product = shipment.carrier.carrier_product
        values['type'] = 'line'

        party = invoice.party
        party_context = {}
        if party.lang:
            party_context['language'] = party.lang.code
        with Transaction().set_context(party_context):
            values['description'] = product_obj.browse(product.id).rec_name

        values['quantity'] = 1 # XXX
        values['unit'] = product.sale_uom.id
        cost = shipment.cost
        if invoice.currency != shipment.cost_currency:
            with Transaction().set_context(date=invoice.currency_date):
                cost = currency_obj.compute(
                    shipment.cost_currency.id,
                    cost, invoice.currency.id)
        values['unit_price'] = cost

        taxes = []
        pattern = self._get_cost_tax_rule_pattern(shipment)
        for tax in product.customer_taxes_used:
            if party.customer_tax_rule:
                tax_ids = tax_rule_obj.apply(party.customer_tax_rule, False,
                        pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        values['taxes'] = [('set', taxes)]

        values['account'] = product.account_revenue_used.id
        if not values['account']:
            self.raise_user_error('missing_account_revenue',
                    error_args=(product.rec_name,))
        return values

ShipmentOut()
