# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.product import price_digits, round_price
from .exceptions import InvoiceShipmentCostError


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    carrier = fields.Many2One('carrier', 'Carrier', states={
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'picked', 'packed']),
            },
        depends=['state'])
    cost = fields.Numeric("Cost",
        digits=price_digits, states={
            'invisible': ~Eval('carrier'),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'packed']),
            }, depends=['carrier', 'state'])
    cost_sale_currency = fields.Many2One(
        'currency.currency', "Cost Sale Currency",
        states={
            'invisible': ~Eval('carrier'),
            'required': Bool(Eval('carrier')),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            }, depends=['carrier', 'state'])
    cost_sale = fields.Numeric(
        "Cost Sale", digits=price_digits,
        states={
            'invisible': ~Eval('carrier'),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            }, depends=['carrier', 'state'])
    cost_invoice_line = fields.Many2One('account.invoice.line',
            'Cost Invoice Line', readonly=True)

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        # Migration from 5.8: rename cost into cost_sale
        if (table_h.column_exist('cost')
                and not table_h.column_exist('cost_sale')):
            table_h.column_rename('cost', 'cost_sale')
        if (table_h.column_exist('cost_currency')
                and not table_h.column_exist('cost_sale_currency')):
            table_h.column_rename('cost_currency', 'cost_sale_currency')
        super().__register__(module)

    def _get_carrier_context(self):
        return {}

    def get_carrier_context(self):
        return self._get_carrier_context()

    @fields.depends(methods=['on_change_inventory_moves'])
    def on_change_carrier(self):
        self.on_change_inventory_moves()

    @fields.depends('carrier', 'company', methods=['_get_carrier_context'])
    def on_change_inventory_moves(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        try:
            super(ShipmentOut, self).on_change_inventory_moves()
        except AttributeError:
            pass
        if not self.carrier:
            self.cost = None
            self.cost_sale = None
            self.cost_sale_currency = None
            return
        with Transaction().set_context(self._get_carrier_context()):
            cost, currency_id = self.carrier.get_purchase_price()
            cost_sale, sale_currency_id = self.carrier.get_sale_price()
        self.cost = round_price(Currency.compute(
                Currency(currency_id), cost, self.company.currency,
                round=False))
        self.cost_sale = round_price(cost_sale)
        self.cost_sale_currency = sale_currency_id

    def _get_cost_tax_rule_pattern(self):
        'Get tax rule pattern for invoice line'
        return {}

    def get_cost_invoice_line(self, invoice):
        pool = Pool()
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')
        InvoiceLine = pool.get('account.invoice.line')

        if not self.cost_sale:
            return
        invoice_line = InvoiceLine()
        product = self.carrier.carrier_product
        invoice_line.type = 'line'
        invoice_line.product = product

        party = invoice.party
        party_context = {}
        if party.lang:
            party_context['language'] = party.lang.code
        with Transaction().set_context(party_context):
            invoice_line.description = Product(product.id).rec_name

        invoice_line.quantity = 1  # XXX
        invoice_line.unit = product.sale_uom.id
        cost = self.cost_sale
        if invoice.currency != self.cost_sale_currency:
            with Transaction().set_context(date=invoice.currency_date):
                cost = Currency.compute(
                    self.cost_sale_currency, cost,
                    invoice.currency, round=False)
        invoice_line.unit_price = round_price(cost)
        invoice_line.currency = invoice.currency
        invoice_line.company = invoice.company

        taxes = []
        pattern = self._get_cost_tax_rule_pattern()
        for tax in product.customer_taxes_used:
            if party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        invoice_line.taxes = taxes

        invoice_line.account = product.account_revenue_used
        if not invoice_line.account:
            raise InvoiceShipmentCostError(
                gettext('sale_shipment_cost'
                    '.msg_shipment_cost_invoice_missing_account_revenue',
                    shipment=self.rec_name,
                    product=product.rec_name))
        return invoice_line

    def _get_shipment_cost(self):
        cost = super()._get_shipment_cost()
        if all(not m.sale.shipment_cost_method for m in self.outgoing_moves):
            cost += self.cost
        return cost
