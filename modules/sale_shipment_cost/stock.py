# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

from .exceptions import InvoiceShipmentCostError


class ShipmentCostSaleMixin:
    __slots__ = ()

    cost_sale_currency_used = fields.Function(fields.Many2One(
            'currency.currency', "Cost Sale Currency",
            states={
                'invisible': Eval('cost_method') != 'shipment',
                'readonly': (
                    Eval('shipment_cost_sale_readonly', True)
                    | ~Eval('cost_edit', False)),
                }),
        'on_change_with_cost_sale_currency_used', setter='set_cost')
    cost_sale_currency = fields.Many2One(
        'currency.currency', "Cost Sale Currency",
        states={
            'invisible': Eval('cost_method') != 'shipment',
            'required': Bool(Eval('cost_sale')),
            'readonly': Eval('shipment_cost_sale_readonly', True),
            })
    cost_sale_used = fields.Function(fields.Numeric(
            "Cost Sale", digits=price_digits,
            states={
                'invisible': Eval('cost_method') != 'shipment',
                'readonly': (
                    Eval('shipment_cost_sale_readonly', True)
                    | ~Eval('cost_edit', False)),
                }),
        'on_change_with_cost_sale_used', setter='set_cost')
    cost_sale = fields.Numeric(
        "Cost Sale", digits=price_digits, readonly=True,
        states={
            'invisible': Eval('cost_method') != 'shipment',
            })

    cost_sales = fields.One2Many(
        'stock.shipment.cost_sale', 'shipment', "Cost Sales", readonly=True)

    cost_invoice_line = fields.Many2One(
        'account.invoice.line', "Cost Invoice Line", readonly=True)
    cost_method = fields.Selection(
        'get_cost_methods', "Cost Method", readonly=True)

    shipment_cost_sale_readonly = fields.Function(
        fields.Boolean("Shipment Cost Sale Read Only"),
        'on_change_with_shipment_cost_sale_readonly')

    def on_change_with_shipment_cost_sale_readonly(self, name=None):
        raise NotImplementedError

    @fields.depends('carrier', 'cost_method', methods=['_get_carrier_context'])
    def _compute_costs(self):
        costs = super()._compute_costs()
        costs.update({
                'cost_sale': None,
                'cost_sale_currency': None,
                })
        if self.carrier and self.cost_method == 'shipment':
            with Transaction().set_context(self._get_carrier_context()):
                cost_sale, sale_currency_id = self.carrier.get_sale_price()
            if cost_sale is not None:
                costs['cost_sale'] = round_price(cost_sale)
            costs['cost_sale_currency'] = sale_currency_id
        return costs

    @fields.depends(
        'shipment_cost_sale_readonly', 'cost_sale', 'cost_edit',
        methods=['_compute_costs'])
    def on_change_with_cost_sale_used(self, name=None):
        if not self.cost_edit and not self.shipment_cost_sale_readonly:
            return self._compute_costs()['cost_sale']
        else:
            return self.cost_sale

    @fields.depends(
        'shipment_cost_sale_readonly', 'cost_sale_currency', 'cost_edit',
        methods=['_compute_costs'])
    def on_change_with_cost_sale_currency_used(self, name=None):
        if not self.cost_edit and not self.shipment_cost_sale_readonly:
            return self._compute_costs()['cost_sale_currency']
        elif self.cost_sale_currency:
            return self.cost_sale_currency

    @classmethod
    def get_cost_methods(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        fieldname = 'shipment_cost_method'
        return Sale.fields_get([fieldname])[fieldname]['selection']

    def get_cost_invoice_line(self, invoice, origin=None):
        pool = Pool()
        Currency = pool.get('currency.currency')
        InvoiceLine = pool.get('account.invoice.line')

        if (self.cost_method != 'shipment'
                or not self.carrier
                or not self.cost_sale_used
                or self.cost_invoice_line):
            return
        product = self.carrier.carrier_product

        invoice_line = InvoiceLine(invoice=invoice, origin=origin)
        invoice_line.on_change_invoice()
        invoice_line.type = 'line'
        invoice_line.quantity = 1  # XXX
        invoice_line.unit = product.sale_uom.id
        cost = self.cost_sale_used
        if invoice.currency != self.cost_sale_currency_used:
            with Transaction().set_context(date=invoice.currency_date):
                cost = Currency.compute(
                    self.cost_sale_currency_used, cost,
                    invoice.currency, round=False)
        invoice_line.unit_price = round_price(cost)
        invoice_line.product = product
        invoice_line.on_change_product()

        if not invoice_line.account:
            raise InvoiceShipmentCostError(
                gettext('sale_shipment_cost'
                    '.msg_shipment_cost_invoice_missing_account_revenue',
                    shipment=self.rec_name,
                    product=product.rec_name))
        return invoice_line

    @property
    def _shipment_cost_currency_date(self):
        raise NotImplementedError

    def _get_shipment_cost(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        transaction = Transaction()
        cost = super()._get_shipment_cost()
        if self.cost_sale:
            with transaction.set_context(
                    date=self._shipment_cost_currency_date):
                cost_sale = Currency.compute(
                    self.cost_sale_currency, self.cost_sale,
                    self.company.currency, round=False)
            cost -= cost_sale
        for line in self.cost_sales:
            with transaction.set_context(date=line.sale.sale_date):
                cost_sale = Currency.compute(
                    line.currency, line.amount,
                    self.company.currency, round=False)
            cost -= cost_sale
        return cost


class ShipmentCostSale(ModelSQL):
    "Shipment Cost Sale"
    __name__ = 'stock.shipment.cost_sale'

    shipment = fields.Reference(
        "Shipment", [
            ('stock.shipment.out', "Customer"),
            ], required=True)
    sale = fields.Many2One('sale.sale', "Sale", required=True)
    amount = fields.Numeric("Amount", digits=price_digits, required=True)
    currency = fields.Many2One('currency.currency', "Currency", required=True)


class ShipmentOut(ShipmentCostSaleMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        # Migration from 5.8: rename cost into cost_sale
        if (table_h.column_exist('cost')
                and not table_h.column_exist('cost_sale')):
            table_h.column_rename('cost', 'cost_sale')
        if (table_h.column_exist('cost_currency')
                and not table_h.column_exist('cost_sale_currency')):
            table_h.column_rename('cost_currency', 'cost_sale_currency')

        cost_method_exists = table_h.column_exist('cost_method')

        super().__register__(module)

        # Migration from 6.0: fill new cost_method field
        if not cost_method_exists:
            cursor.execute(*table.update(
                    columns=[table.cost_method],
                    values=['shipment']))

    @fields.depends('state')
    def on_change_with_shipment_cost_sale_readonly(self, name=None):
        return self.state in {'done', 'cancelled'}

    @property
    def _shipment_cost_currency_date(self):
        return self.effective_date

    def get_cost_invoice_line(self, invoice, origin=None):
        invoice_line = super().get_cost_invoice_line(invoice, origin=origin)
        if invoice_line:
            invoice_line.cost_shipments = [self]
        return invoice_line

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        for shipment in shipments:
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
            shipment.cost_sales = None
        cls.save(shipments)
        super().cancel(shipments)
