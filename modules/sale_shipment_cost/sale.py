#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool
from trytond.pool import Pool, PoolMeta

__all__ = ['Configuration', 'Sale', 'SaleLine']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'sale.configuration'
    sale_carrier = fields.Property(fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
    ))
    sale_shipment_cost_method = fields.Property(fields.Selection([
                ('order', 'On Order'),
                ('shipment', 'On Shipment'),
                ], 'Sale Shipment Cost Method',
            states={
                'required': Bool(Eval('context', {}).get('company', 0)),
                }))

    @staticmethod
    def default_sale_shipment_cost_method():
        return 'shipment'


class Sale:
    __name__ = 'sale.sale'
    carrier = fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
        on_change=['carrier', 'party', 'currency', 'sale_date'],
        states={
            'readonly': Eval('state') != 'draft',
        },
        depends=['state'])
    shipment_cost_method = fields.Selection([
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
        ], 'Shipment Cost Method', required=True, states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

        for fname in ('carrier', 'party', 'currency', 'sale_date',
                'shipment_cost_method', 'lines'):
            if fname not in cls.lines.on_change:
                cls.lines.on_change.append(fname)
        for fname in cls.lines.on_change:
            if fname not in cls.carrier.on_change:
                cls.carrier.on_change.append(fname)

    @staticmethod
    def default_carrier():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_carrier.id if config.sale_carrier else None

    @staticmethod
    def default_shipment_cost_method():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_shipment_cost_method

    def _get_carrier_context(self):
        return {}

    def on_change_carrier(self):
        return self.on_change_lines()

    def on_change_lines(self):
        pool = Pool()
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')
        SaleLine = pool.get('sale.line')
        Date = pool.get('ir.date')

        today = Date.today()

        cost, currency_id = 0, None
        if self.carrier:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_sale_price()

        party = None
        party_context = {}
        if self.party:
            if self.party.lang:
                party_context['language'] = self.party.lang.code

        cost_line = {}
        products = [line.product for line in self.lines or []
                if line.product]
        stockable = any(product.type in ('goods', 'assets')
            for product in products)
        if cost and currency_id and stockable:
            if (self.currency
                    and currency_id != self.currency.id):
                date = self.sale_date or today
                with Transaction().set_context(date=date):
                    cost = Currency.compute(Currency(currency_id), cost,
                        self.currency)
            product = self.carrier.carrier_product
            with Transaction().set_context(party_context):
                description = Product(product.id).rec_name
            taxes = []
            cost_line = SaleLine.default_get(SaleLine._fields.keys())
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
            pattern = SaleLine(**cost_line)._get_tax_rule_pattern()
            for tax in product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)

        to_remove = None
        operator, operand = None, None
        if not self.lines:
            self.lines = []
        for line in self.lines:
            if line.shipment_cost:
                if line.shipment_cost != cost_line.get('shipment_cost'):
                    to_remove = line.id
                    self.lines.remove(line)
                    if cost_line:
                        cost_line['description'] = line.description
                else:
                    cost_line = {}
                break
        if cost_line:
            self.lines.append(SaleLine(**cost_line))

        result = super(Sale, self).on_change_lines()

        lines = result.setdefault('lines', {})
        if to_remove:
            lines.setdefault('remove', []).append(to_remove)
        if cost_line:
            lines.setdefault('add', []).append(cost_line)
        return result

    def create_shipment(self, shipment_type):
        Shipment = Pool().get('stock.shipment.out')

        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out' and shipments and self.carrier:
            for shipment in shipments:
                shipment.carrier = self.carrier
                with Transaction().set_context(
                        shipment.get_carrier_context()):
                    cost, currency_id = self.carrier.get_sale_price()
                with Transaction().set_user(0, set_context=True):
                    Shipment.write([shipment], {
                            'carrier': self.carrier.id,
                            'cost': cost,
                            'cost_currency': currency_id,
                            })
        return shipments

    def _get_invoice_line_sale_line(self, invoice_type):
        result = super(Sale, self)._get_invoice_line_sale_line(invoice_type)
        if self.shipment_cost_method == 'shipment':
            for line in self.lines:
                if line.id in result and line.shipment_cost:
                    del result[line.id]
        return result

    def create_invoice(self, invoice_type):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Shipment = pool.get('stock.shipment.out')

        invoice = super(Sale, self).create_invoice(invoice_type)
        if (invoice
                and invoice_type == 'out_invoice'
                and self.shipment_cost_method == 'shipment'):
            with Transaction().set_user(0, set_context=True):
                invoice = Invoice(invoice.id)
            for shipment in self.shipments:
                if (shipment.state == 'done'
                        and shipment.carrier
                        and shipment.cost
                        and not shipment.cost_invoice_line):
                    invoice_line = shipment.get_cost_invoice_line(invoice)
                    if not invoice_line:
                        continue
                    invoice_line.invoice = invoice
                    invoice_line.save()
                    Shipment.write([shipment], {
                            'cost_invoice_line': invoice_line.id,
                            })
            with Transaction().set_user(0, set_context=True):
                Invoice.update_taxes([invoice])
        return invoice


class SaleLine:
    __name__ = 'sale.line'
    shipment_cost = fields.Numeric('Shipment Cost',
        digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)))
