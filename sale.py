# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, If
from trytond.pool import Pool, PoolMeta

from trytond.modules.product import price_digits, round_price
from trytond.modules.sale.exceptions import SaleConfirmError

sale_shipment_cost_method = fields.Selection(
        'get_sale_shipment_cost_methods', "Sale Shipment Cost Method")


def get_sale_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get([field_name])[field_name]['selection']
    return func


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'
    sale_shipment_cost_method = fields.MultiValue(sale_shipment_cost_method)
    get_sale_shipment_cost_methods = get_sale_methods('shipment_cost_method')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_shipment_cost_method':
            return pool.get('sale.configuration.sale_method')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_sale_shipment_cost_method(cls, **pattern):
        return cls.multivalue_model(
            'sale_shipment_cost_method').default_sale_shipment_cost_method()


class ConfigurationSaleMethod(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sale_method'
    sale_shipment_cost_method = sale_shipment_cost_method
    get_sale_shipment_cost_methods = get_sale_methods('shipment_cost_method')

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= table.column_exist('sale_shipment_cost_method')

        super(ConfigurationSaleMethod, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sale_shipment_cost_method')
        value_names.append('sale_shipment_cost_method')
        super(ConfigurationSaleMethod, cls)._migrate_property(
            field_names, value_names, fields)

    @classmethod
    def default_sale_shipment_cost_method(cls):
        return 'order'


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'
    carrier = fields.Many2One('carrier', 'Carrier',
        domain=[
            If(Eval('state') == 'draft', [
                    ('carrier_product.salable', '=', True),
                    ('id', 'in', Eval('available_carriers', [])),
                    ],
                []),
            ],
        states={
            'readonly': Eval('state') != 'draft',
        },
        context={
            'company': Eval('company', -1),
            },
        depends=['state', 'available_carriers', 'company'])
    available_carriers = fields.Function(
        fields.Many2Many('carrier', None, None, 'Available Carriers'),
        'on_change_with_available_carriers')
    shipment_cost_method = fields.Selection([
        (None, "None"),
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
        ], 'Shipment Cost Method', states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])

    @classmethod
    def __register__(cls, module):
        super().__register__(module)
        table_h = cls.__table_handler__(module)
        # Migration from 5.8: remove required on shipment_cost_method
        table_h.not_null_action('shipment_cost_method', 'remove')

    @classmethod
    def default_shipment_cost_method(cls, **pattern):
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.get_multivalue(
            'sale_shipment_cost_method', **pattern)

    @fields.depends('company')
    def on_change_company(self):
        super().on_change_company()
        self.shipment_cost_method = self.default_shipment_cost_method(
            company=self.company.id if self.company else None)

    @fields.depends('warehouse', 'shipment_address')
    def _get_carrier_selection_pattern(self):
        pattern = {}
        if (self.warehouse
                and self.warehouse.address
                and self.warehouse.address.country):
            pattern['from_country'] = self.warehouse.address.country.id
        else:
            pattern['from_country'] = None
        if self.shipment_address and self.shipment_address.country:
            pattern['to_country'] = self.shipment_address.country.id
        else:
            pattern['to_country'] = None
        return pattern

    @fields.depends(methods=['_get_carrier_selection_pattern'])
    def on_change_with_available_carriers(self, name=None):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')

        pattern = self._get_carrier_selection_pattern()
        carriers = CarrierSelection.get_carriers(pattern)
        return [c.id for c in carriers]

    @fields.depends('carrier', methods=['on_change_with_available_carriers'])
    def on_change_party(self):
        super(Sale, self).on_change_party()
        self.available_carriers = self.on_change_with_available_carriers()
        if self.available_carriers and (not self.carrier
                or self.carrier not in self.available_carriers):
            self.carrier = self.available_carriers[0]
        elif not self.available_carriers:
            self.carrier = None

    @fields.depends('carrier', methods=['on_change_with_available_carriers'])
    def on_change_shipment_party(self):
        super(Sale, self).on_change_shipment_party()
        self.available_carriers = self.on_change_with_available_carriers()
        if self.available_carriers and (not self.carrier
                or self.carrier not in self.available_carriers):
            self.carrier = self.available_carriers[0]
        elif not self.available_carriers:
            self.carrier = None

    @fields.depends('carrier', methods=['on_change_with_available_carriers'])
    def on_change_shipment_address(self):
        try:
            super_on_change = super(Sale, self).on_change_shipment_address
        except AttributeError:
            pass
        else:
            super_on_change()

        self.available_carriers = self.on_change_with_available_carriers()
        if self.available_carriers and (not self.carrier
                or self.carrier not in self.available_carriers):
            self.carrier = self.available_carriers[0]
        elif not self.available_carriers:
            self.carrier = None

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        pool = Pool()
        Line = pool.get('sale.line')
        removed = []
        for sale in sales:
            removed.extend(sale.set_shipment_cost())
        Line.delete(removed)
        cls.save(sales)
        super(Sale, cls).quote(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        for sale in sales:
            if sale.carrier and sale.carrier not in sale.available_carriers:
                raise SaleConfirmError(
                    gettext('sale_shipment_cost.msg_sale_invalid_carrier',
                        sale=sale.rec_name,
                        carrier=sale.carrier.rec_name))
        super(Sale, cls).confirm(sales)

    def _get_carrier_context(self):
        return {}

    def compute_shipment_cost(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Currency = pool.get('currency.currency')
        Move = pool.get('stock.move')
        stockable = any(
            line.quantity >= 0 for line in self.lines
            if line.type == 'line'
            and line.product
            and line.product.type in Move.get_product_types())
        if self.carrier and stockable:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_sale_price()
            today = Date.today()
            date = self.sale_date or today
            with Transaction().set_context(date=date):
                return Currency.compute(
                    Currency(currency_id), cost, self.currency, round=False)

    def set_shipment_cost(self):
        cost = None
        if self.shipment_cost_method:
            cost = self.compute_shipment_cost()
        removed = []
        unit_price = None
        lines = list(self.lines or [])
        for line in self.lines:
            if line.type == 'line' and line.shipment_cost is not None:
                if line.shipment_cost == cost:
                    unit_price = line.unit_price * Decimal(str(line.quantity))
                lines.remove(line)
                removed.append(line)
        if cost is not None:
            lines.append(self.get_shipment_cost_line(
                    cost, unit_price=unit_price))
        self.lines = lines
        return removed

    def get_shipment_cost_line(self, cost, unit_price=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        product = self.carrier.carrier_product

        sequence = None
        if self.lines:
            last_line = self.lines[-1]
            if last_line.sequence is not None:
                sequence = last_line.sequence + 1

        shipment_cost = round_price(cost)
        cost_line = SaleLine(
            sale=self,
            sequence=sequence,
            type='line',
            product=product,
            quantity=1,  # XXX
            unit=product.sale_uom,
            shipment_cost=shipment_cost,
            )
        cost_line.on_change_product()
        if unit_price is not None:
            cost_line.unit_price = round_price(unit_price)
        else:
            cost_line.unit_price = round_price(cost)
        if not cost_line.unit_price:
            cost_line.quantity = 0
        cost_line.amount = cost_line.on_change_with_amount()
        return cost_line

    @property
    def shipment_cost_amount(self):
        cost = Decimal(0)
        for line in self.lines:
            if line.type == 'line' and line.shipment_cost is not None:
                cost += line.amount
        return cost

    def create_shipment(self, shipment_type):
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')

        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out' and shipments and self.carrier:
            for shipment in shipments:
                shipment.carrier = self.carrier
        Shipment.save(shipments)
        return shipments

    def create_invoice(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Shipment = pool.get('stock.shipment.out')

        invoice = super(Sale, self).create_invoice()
        if invoice and self.shipment_cost_method == 'shipment':
            invoice_lines = []
            # Copy shipments to avoid losing changes as the cache is cleared
            # after invoice line save because shipment is a Function field
            shipments = list(self.shipments)
            for shipment in shipments:
                if (shipment.state == 'done'
                        and shipment.carrier
                        and not shipment.cost_invoice_line):
                    invoice_line = shipment.get_cost_invoice_line(invoice)
                    if not invoice_line:
                        continue
                    invoice_line.invoice = invoice
                    invoice_lines.append(invoice_line)
                    shipment.cost_invoice_line = invoice_line
            InvoiceLine.save(invoice_lines)
            Shipment.save(shipments)
            invoice.update_taxes()
        return invoice


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'
    shipment_cost = fields.Numeric('Shipment Cost', digits=price_digits)

    def _get_invoice_line_quantity(self):
        quantity = super()._get_invoice_line_quantity()
        if self.shipment_cost:
            if self.sale.shipment_cost_method == 'shipment':
                return 0
            elif (self.sale.shipment_cost_method == 'order'
                    and self.sale.invoice_method == 'shipment'):
                shipments = self.sale.shipments
                if (not shipments
                        or all(s.state != 'done' for s in shipments)):
                    return 0
        return quantity


class ReturnSale(metaclass=PoolMeta):
    __name__ = 'sale.return_sale'

    def do_return_(self, action):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        action, data = super(ReturnSale, self).do_return_(action)

        return_sales = Sale.browse(data['res_id'])
        lines = []
        for sale in return_sales:
            for line in sale.lines:
                # Do not consider return shipment cost as a shipment cost
                if line.shipment_cost:
                    line.shipment_cost = None
                    lines.append(line)
        SaleLine.save(lines)
        return action, data


class Promotion(metaclass=PoolMeta):
    __name__ = 'sale.promotion'

    amount_shipment_cost_included = fields.Boolean(
        "Amount with Shipment Cost Included",
        states={
            'invisible': ~Eval('amount'),
            },
        depends=['amount'])

    @classmethod
    def default_amount_shipment_cost_included(cls):
        return False

    def get_context_formula(self, sale_line):
        context = super(Promotion, self).get_context_formula(sale_line)
        if sale_line and sale_line.shipment_cost:
            context['names']['unit_price'] = sale_line.shipment_cost
        return context

    def get_sale_amount(self, sale):
        amount = super().get_sale_amount(sale)
        if not self.amount_shipment_cost_included:
            amount -= sum(l.amount for l in sale.lines if l.shipment_cost)
            if not self.untaxed_amount:
                amount -= sum(
                    v['amount']
                    for l in sale.lines if l.shipment_cost
                    for v in l._get_taxes().values())
        return amount
