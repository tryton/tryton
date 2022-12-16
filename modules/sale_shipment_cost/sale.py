#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import copy
from trytond.model import Model, fields
from trytond.transaction import Transaction
from trytond.pyson import Not, Equal, Eval, Bool, Get


class Configuration(Model):
    _name = 'sale.configuration'

    sale_carrier = fields.Property(fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
    ))
    sale_shipment_cost_method = fields.Property(fields.Selection([
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
    ], 'Sale Shipment Cost Method', states={
        'required': Bool(Eval('company')),
    }))

    def default_sale_shipment_cost_method(self):
        return 'shipment'


Configuration()


class Sale(Model):
    _name = 'sale.sale'

    carrier = fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
        on_change=['carrier', 'party', 'currency', 'sale_date'],
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
        })
    shipment_cost_method = fields.Selection([
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
        ], 'Shipment Cost Method', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['state'])

    def __init__(self):
        super(Sale, self).__init__()

        self.lines = copy.copy(self.lines)
        self.lines.on_change = copy.copy(self.lines.on_change)
        for fname in ('carrier', 'party', 'currency', 'sale_date',
                'shipment_cost_method', 'lines'):
            if fname not in self.lines.on_change:
                self.lines.on_change.append(fname)
        self.carrier = copy.copy(self.carrier)
        self.carrier.on_change = copy.copy(self.carrier.on_change)
        for fname in self.lines.on_change:
            if fname not in self.carrier.on_change:
                self.carrier.on_change.append(fname)
        self._reset_columns()

    def default_carrier(self):
        config_obj = self.pool.get('sale.configuration')
        config = config_obj.browse(1)
        return config.sale_carrier.id

    def default_shipment_cost_method(self):
        config_obj = self.pool.get('sale.configuration')
        config = config_obj.browse(1)
        return config.sale_shipment_cost_method

    def _get_carrier_context(self, values):
        return {}

    def on_change_carrier(self, values):
        return self.on_change_lines(values)

    def on_change_lines(self, values):
        carrier_obj = self.pool.get('carrier')
        party_obj = self.pool.get('party.party')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('currency.currency')
        sale_line_obj = self.pool.get('sale.line')
        tax_rule_obj = self.pool.get('account.tax.rule')
        date_obj = self.pool.get('ir.date')

        today = date_obj.today()

        cost, currency_id = 0, False
        if values.get('carrier'):
            carrier = carrier_obj.browse(values['carrier'])
            with Transaction().set_context(
                self._get_carrier_context(values)):
                cost, currency_id = carrier_obj.get_sale_price(carrier)

        party = None
        party_context = {}
        if values.get('party'):
            party = party_obj.browse(values['party'])
            if party.lang:
                party_context['language'] = party.lang.code

        cost_line = {}
        product_ids = [line['product'] for line in values.get('lines') or []
                if line.get('product')]
        stockable = any(product.type in ('stockable', 'consumable')
            for product in product_obj.browse(product_ids))
        if cost and currency_id and stockable:
            if (values.get('currency')
                    and currency_id != values['currency']):
                date = values.get('sale_date') or today
                with Transaction().set_context(date=date):
                    cost = currency_obj.compute(currency_id, cost,
                        values['currency'])
            product = carrier.carrier_product
            with Transaction().set_context(party_context):
                description = product_obj.browse(product.id).rec_name
            taxes = []
            cost_line = sale_line_obj.default_get(
                sale_line_obj._columns.keys())
            cost_line.update({
                    'type': 'line',
                    'product': product.id,
                    'description': description,
                    'quantity': 1,  # XXX
                    'unit': product.sale_uom.id,
                    'unit_price': cost,
                    'shipment_cost': cost,
                    'amount': cost,
                    'taxes': taxes,
                    'sequence': 9999,  # XXX
                    })
            pattern = sale_line_obj._get_tax_rule_pattern(party,
                cost_line)
            for tax in product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = tax_rule_obj.apply(party.customer_tax_rule,
                        tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = tax_rule_obj.apply(party.customer_tax_rule, False,
                    pattern)
                if tax_ids:
                    taxes.extend(tax_ids)

        to_remove = None
        operator, operand = None, None
        values = values.copy()
        if not values.get('lines'):
            values['lines'] = []
        for line in values['lines']:
            if line.get('shipment_cost'):
                if line['shipment_cost'] != cost_line.get('shipment_cost'):
                    to_remove = line['id']
                    values['lines'].remove(line)
                    if cost_line:
                        del cost_line['description']
                        line.update(cost_line)
                        cost_line = line
                        del cost_line['id']
                else:
                    cost_line = {}
                break
        if cost_line:
            values['lines'].append(cost_line)

        result = super(Sale, self).on_change_lines(values)

        lines = result.setdefault('lines', {})
        if to_remove:
            lines.setdefault('remove', []).append(to_remove)
        if cost_line:
            lines.setdefault('add', []).append(cost_line)
        return result

    def create_shipment(self, sale_id):
        shipment_obj = self.pool.get('stock.shipment.out')
        carrier_obj = self.pool.get('carrier')

        shipment_id = super(Sale, self).create_shipment(sale_id)
        sale = self.browse(sale_id)
        if shipment_id and sale.carrier:
            shipment = shipment_obj.browse(shipment_id)
            with Transaction().set_context(
                    shipment_obj.get_carrier_context(shipment)):
                cost, currency_id = carrier_obj.get_sale_price(sale.carrier)
            with Transaction().set_user(0, set_context=True):
                shipment_obj.write(shipment_id, {
                    'carrier': sale.carrier.id,
                    'cost': cost,
                    'cost_currency': currency_id,
                })
        return shipment_id

    def _get_invoice_line_sale_line(self, sale):
        result = super(Sale, self)._get_invoice_line_sale_line(sale)
        if sale.shipment_cost_method == 'shipment':
            for line in sale.lines:
                if line.id in result and line.shipment_cost:
                    del result[line.id]
        return result

    def create_invoice(self, sale_id):
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        shipment_obj = self.pool.get('stock.shipment.out')

        invoice_id = super(Sale, self).create_invoice(sale_id)
        sale = self.browse(sale_id)
        if (invoice_id
                and sale.shipment_cost_method == 'shipment'):
            with Transaction().set_user(0, set_context=True):
                invoice = invoice_obj.browse(invoice_id)
            for shipment in sale.shipments:
                if (shipment.state == 'done'
                        and shipment.carrier
                        and shipment.cost
                        and not shipment.cost_invoice_line):
                    vals = shipment_obj.get_cost_invoice_line(
                            shipment, invoice)
                    if not vals:
                        continue
                    vals['invoice'] = invoice_id
                    with Transaction().set_user(0, set_context=True):
                        invoice_line_id = invoice_line_obj.create(vals)
                    shipment_obj.write(shipment.id, {
                        'cost_invoice_line': invoice_line_id,
                        })
            with Transaction().set_user(0, set_context=True):
                invoice_obj.update_taxes([invoice_id])
        return invoice_id

Sale()


class SaleLine(Model):
    _name = 'sale.line'

    shipment_cost = fields.Numeric('Shipment Cost',
        digits=(16, Get(Eval('_parent_sale', {}), 'currency_digits', 2)))

SaleLine()
