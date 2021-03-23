# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
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

    cost_used = fields.Function(fields.Numeric(
            "Cost", digits=price_digits,
            states={
                'invisible': ~Eval('carrier') | Eval('cost_edit', False),
                },
            depends=['carrier', 'cost_edit']),
        'on_change_with_cost_used')
    cost = fields.Numeric(
        "Cost", digits=price_digits,
        states={
            'invisible': ~Eval('carrier') | ~Eval('cost_edit', False),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            },
        depends=['carrier', 'state'])
    cost_sale_currency_used = fields.Function(fields.Many2One(
            'currency.currency', "Cost Sale Currency",
            states={
                'invisible': ~Eval('carrier') | Eval('cost_edit', False),
                },
            depends=['carrier', 'cost_edit']),
        'on_change_with_cost_sale_currency_used')
    cost_sale_currency = fields.Many2One(
        'currency.currency', "Cost Sale Currency",
        states={
            'invisible': ~Eval('carrier') | ~Eval('cost_edit', False),
            'required': Bool(Eval('cost_sale')),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            }, depends=['carrier', 'cost_sale', 'state'])
    cost_sale_used = fields.Function(fields.Numeric(
            "Cost Sale", digits=price_digits,
            states={
                'invisible': ~Eval('carrier') | Eval('cost_edit', False),
                },
            depends=['carrier', 'cost_edit']),
        'on_change_with_cost_sale_used')
    cost_sale = fields.Numeric(
        "Cost Sale", digits=price_digits,
        states={
            'invisible': ~Eval('carrier') | ~Eval('cost_edit', False),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            }, depends=['carrier', 'state'])

    cost_edit = fields.Boolean(
        "Edit Cost",
        states={
            'invisible': ~Eval('carrier'),
            'readonly': ~Eval('state').in_(
                ['draft', 'waiting', 'assigned', 'picked', 'packed']),
            },
        depends=['carrier', 'state'],
        help="Check to edit the cost.")

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

    @fields.depends('carrier', 'company', methods=['_get_carrier_context'])
    def _compute_costs(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        costs = {
            'cost': None,
            'cost_sale': None,
            'cost_sale_currency': None,
            }
        if self.carrier:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_purchase_price()
                cost_sale, sale_currency_id = self.carrier.get_sale_price()
            if cost is not None:
                cost = Currency.compute(
                    Currency(currency_id), cost, self.company.currency,
                    round=False)
                costs['cost'] = round_price(cost)
            if cost_sale is not None:
                costs['cost_sale'] = round_price(cost_sale)
            costs['cost_sale_currency'] = sale_currency_id
        return costs

    @fields.depends('state', 'cost', 'cost_edit', methods=['_compute_costs'])
    def on_change_with_cost_used(self, name=None):
        if not self.cost_edit and self.state not in {'cancelled', 'done'}:
            return self._compute_costs()['cost']
        else:
            return self.cost

    @fields.depends(
        'state', 'cost_sale', 'cost_edit', methods=['_compute_costs'])
    def on_change_with_cost_sale_used(self, name=None):
        if not self.cost_edit and self.state not in {'cancelled', 'done'}:
            return self._compute_costs()['cost_sale']
        else:
            return self.cost_sale

    @fields.depends(
        'state', 'cost_sale_currency', 'cost_edit', methods=['_compute_costs'])
    def on_change_with_cost_sale_currency_used(self, name=None):
        if not self.cost_edit and self.state not in {'cancelled', 'done'}:
            return self._compute_costs()['cost_sale_currency']
        elif self.cost_sale_currency:
            return self.cost_sale_currency.id

    @fields.depends(
        'cost_edit', 'cost_used', 'cost_sale_used', 'cost_sale_currency_used')
    def on_change_cost_edit(self):
        if self.cost_edit:
            self.cost = self.cost_used
            self.cost_sale = self.cost_sale_used
            self.cost_sale_currency = self.cost_sale_currency_used

    def _get_cost_tax_rule_pattern(self):
        'Get tax rule pattern for invoice line'
        return {}

    def get_cost_invoice_line(self, invoice):
        pool = Pool()
        Product = pool.get('product.product')
        Currency = pool.get('currency.currency')
        InvoiceLine = pool.get('account.invoice.line')

        if not self.cost_sale_used:
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
        cost = self.cost_sale_used
        if invoice.currency != self.cost_sale_currency_used:
            with Transaction().set_context(date=invoice.currency_date):
                cost = Currency.compute(
                    self.cost_sale_currency_used, cost,
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
        pool = Pool()
        Currency = pool.get('currency.currency')
        cost = super()._get_shipment_cost()
        methods = {
            m.sale.shipment_cost_method for m in self.outgoing_moves if m.sale}
        if methods == {None}:
            cost += self.cost_used or 0
        if 'shipment' in methods:
            if self.cost_sale:
                cost_sale = Currency.compute(
                    self.cost_sale_currency, self.cost_sale,
                    self.company.currency, round=False)
            else:
                cost_sale = 0
            delta = cost_sale - (self.cost_used or 0)
            if delta < 0:
                cost -= delta
        if 'order' in methods and self.cost_used:
            sales = {
                m.sale for m in self.outgoing_moves
                if m.sale and m.sale.shipment_cost_method == 'order'}
            for sale in sales:
                shipment_cost = sum(
                    (s.cost_used or 0) for s in sale.shipments
                    if s.state == 'done' and s != self)
                cost_sale = sale.shipment_cost_amount
                if cost_sale < shipment_cost:
                    cost += self.cost_used or 0
                elif cost_sale < shipment_cost + (self.cost_used or 0):
                    cost += shipment_cost + self.cost_used - cost_sale
        return cost

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        for shipment in shipments:
            shipment.cost = shipment.cost_used
            shipment.cost_sale = shipment.cost_sale_used
            shipment.cost_sale_currency = shipment.cost_sale_currency_used
        cls.save(shipments)
        super().done(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, shipments):
        for shipment in shipments:
            shipment.cost = None
            shipment.cost_sale = None
            shipment.cost_sale_currency = None
        cls.save(shipments)
        super().cancel(shipments)
