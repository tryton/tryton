# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.product import price_digits

__all__ = ['ShipmentOut']


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    carrier = fields.Many2One('carrier', 'Carrier', states={
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'packed']),
            },
        depends=['state'])
    cost_currency = fields.Many2One('currency.currency',
        'Cost Currency', states={
            'invisible': ~Eval('carrier'),
            'required': Bool(Eval('carrier')),
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'packed']),
            }, depends=['carrier', 'state'])
    cost = fields.Numeric('Cost',
        digits=price_digits, states={
            'invisible': ~Eval('carrier'),
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned',
                    'packed']),
            }, depends=['carrier', 'state'])
    cost_invoice_line = fields.Many2One('account.invoice.line',
            'Cost Invoice Line', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'missing_account_revenue': ('Missing "Account Revenue" on '
                    'product "%s".'),
                })

    def _get_carrier_context(self):
        return {}

    def get_carrier_context(self):
        return self._get_carrier_context()

    @fields.depends(methods=['on_change_inventory_moves'])
    def on_change_carrier(self):
        self.on_change_inventory_moves()

    @fields.depends('carrier', 'customer', 'inventory_moves',
        methods=['_get_carrier_context'])
    def on_change_inventory_moves(self):
        try:
            super(ShipmentOut, self).on_change_inventory_moves()
        except AttributeError:
            pass
        if not self.carrier:
            return
        with Transaction().set_context(self._get_carrier_context()):
            cost, currency_id = self.carrier.get_sale_price()
        self.cost = cost.quantize(
            Decimal(1) / 10 ** self.__class__.cost.digits[1])
        self.cost_currency = currency_id

    def _get_cost_tax_rule_pattern(self):
        'Get tax rule pattern for invoice line'
        return {}

    def get_cost_invoice_line(self, invoice):
        pool = Pool()
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')
        InvoiceLine = pool.get('account.invoice.line')

        if not self.cost:
            return {}
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
        cost = self.cost
        if invoice.currency != self.cost_currency:
            with Transaction().set_context(date=invoice.currency_date):
                cost = Currency.compute(self.cost_currency, cost,
                    invoice.currency, round=False)
        invoice_line.unit_price = cost.quantize(
            Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])

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
            self.raise_user_error('missing_account_revenue',
                    error_args=(product.rec_name,))
        return invoice_line
