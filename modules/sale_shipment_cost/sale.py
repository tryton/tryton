# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Null

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.modules.product import price_digits, round_price
from trytond.modules.sale.exceptions import (
    SaleConfirmError, SaleQuotationError)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

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
        depends={'company'})
    available_carriers = fields.Function(
        fields.Many2Many('carrier', None, None, 'Available Carriers'),
        'on_change_with_available_carriers')
    shipment_cost_method = fields.Selection([
            (None, "None"),
            ('order', "On Order"),
            ('shipment', "On Shipment"),
            ], "Shipment Cost Method",
        domain=[
            If(~Eval('carrier') & ~Eval('state').in_(['draft', 'cancelled']),
                ('shipment_cost_method', '=', None),
                ()),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    shipment_costs = fields.One2Many(
        'stock.shipment.cost_sale', 'sale', "Shipment Costs", readonly=True)

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super().__register__(module)
        table_h = cls.__table_handler__(module)
        # Migration from 5.8: remove required on shipment_cost_method
        table_h.not_null_action('shipment_cost_method', 'remove')

        # Migration from 6.6: shipment_cost_method domain
        cursor.execute(*table.update(
                [table.shipment_cost_method],
                [Null],
                where=(table.carrier == Null) & (table.state != 'draft')))

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

    @fields.depends(
        'warehouse', 'shipment_address',
        methods=['_get_carrier_selection_pattern'])
    def on_change_with_available_carriers(self, name=None):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')

        if (self.warehouse
                and self.shipment_address
                and self.warehouse.address == self.shipment_address):
            return []

        pattern = self._get_carrier_selection_pattern()
        return CarrierSelection.get_carriers(pattern)

    @fields.depends('carrier', methods=['on_change_with_available_carriers'])
    def on_change_party(self):
        super(Sale, self).on_change_party()
        if self.party and self.party.sale_shipment_cost_method != 'default':
            self.shipment_cost_method = self.party.sale_shipment_cost_method
        else:
            self.shipment_cost_method = self.default_shipment_cost_method()
        self.available_carriers = self.on_change_with_available_carriers()
        if not self.available_carriers:
            self.carrier = None
        elif self.shipment_cost_method:
            if (not self.carrier
                    or self.carrier not in self.available_carriers):
                self.carrier = self.available_carriers[0]

    @fields.depends(
        'carrier', 'shipment_cost_method',
        methods=['on_change_with_available_carriers'])
    def on_change_shipment_party(self):
        super(Sale, self).on_change_shipment_party()
        self.available_carriers = self.on_change_with_available_carriers()
        if not self.available_carriers:
            self.carrier = None
        elif self.shipment_cost_method:
            if (not self.carrier
                    or self.carrier not in self.available_carriers):
                self.carrier = self.available_carriers[0]

    @fields.depends(
        'carrier', 'shipment_cost_method',
        methods=['on_change_with_available_carriers'])
    def on_change_shipment_address(self):
        try:
            super_on_change = super(Sale, self).on_change_shipment_address
        except AttributeError:
            pass
        else:
            super_on_change()

        self.available_carriers = self.on_change_with_available_carriers()
        if not self.available_carriers:
            self.carrier = None
        elif self.shipment_cost_method:
            if (not self.carrier
                    or self.carrier not in self.available_carriers):
                self.carrier = self.available_carriers[0]

    def check_for_quotation(self):
        super().check_for_quotation()
        if self.shipment_cost_method and self.available_carriers:
            for line in self.lines:
                if (line.product
                        and line.product.type != 'service'
                        and line.quantity >= 0
                        and not self.carrier):
                    raise SaleQuotationError(
                        gettext('sale_shipment_cost'
                            '.msg_sale_carrier_required_for_quotation',
                            sale=self.rec_name))

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

    @classmethod
    @ModelView.button
    def process(cls, sales):
        with Transaction().set_context(_shipment_cost_invoiced=list()):
            super().process(sales)

    @classmethod
    def _process_invoice_shipment_states(cls, sales):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentCostSale = pool.get('stock.shipment.cost_sale')

        sent, not_sent = [], []
        for sale in sales:
            if sale.shipment_cost_method == 'order':
                if sale.shipment_state == 'sent':
                    sent.append(sale)
                else:
                    not_sent.append(sale)

        super()._process_invoice_shipment_states(sales)

        to_save, to_delete, shipments = [], [], set()
        for sale in sent:
            if sale.shipment_state != 'sent':
                to_delete.extend(sale.shipment_costs)
                shipments.update(sale.shipments)
        for sale in not_sent:
            if sale.shipment_state == 'sent':
                to_save.extend(sale._get_shipment_costs())
                shipments.update(sale.shipments)

        ShipmentCostSale.delete(to_delete)
        ShipmentCostSale.save(to_save)
        ShipmentOut.set_shipment_cost(shipments)

    @property
    def _cost_shipments(self):
        "Return the shipments to apply cost sale"
        return [s for s in self.shipments if s.state != 'cancelled']

    def _get_shipment_costs(self):
        "Yield shipment costs"
        pool = Pool()
        ShipmentCostSale = pool.get('stock.shipment.cost_sale')
        cost = self.shipment_cost_amount
        shipments = self._cost_shipments
        sum_ = sum(s.cost_used for s in shipments if s.cost_used)
        for shipment in shipments:
            if sum_:
                factor = (shipment.cost_used or 0) / sum_
            else:
                factor = Decimal(1) / len(shipments)
            yield ShipmentCostSale(
                shipment=shipment,
                sale=self,
                amount=round_price(cost * factor),
                currency=self.currency)

    def _get_carrier_context(self, carrier):
        return {}

    def compute_shipment_cost(self, carrier):
        pool = Pool()
        Date = pool.get('ir.date')
        Currency = pool.get('currency.currency')
        Line = pool.get('sale.line')
        stockable = any(
            line.quantity >= 0 for line in self.lines
            if line.type == 'line'
            and line.product
            and line.product.type in Line.get_move_product_types())
        if stockable:
            with Transaction().set_context(self._get_carrier_context(carrier)):
                cost, currency_id = carrier.get_sale_price()
            if cost is not None:
                with Transaction().set_context(company=self.company.id):
                    today = Date.today()
                date = self.sale_date or today
                with Transaction().set_context(date=date):
                    return Currency.compute(
                        Currency(currency_id),
                        cost, self.currency, round=False)

    def set_shipment_cost(self):
        cost = None
        if self.carrier and self.shipment_cost_method:
            cost = self.compute_shipment_cost(self.carrier)
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
                    self.carrier, cost, unit_price=unit_price))
        self.lines = lines
        return removed

    def get_shipment_cost_line(self, carrier, cost, unit_price=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        product = carrier.carrier_product

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
        cost_line.amount = cost_line.on_change_with_amount()
        return cost_line

    def _get_shipment_grouping_fields(self, shipment):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        fields = super()._get_shipment_grouping_fields(shipment)
        fields.append('carrier')
        if isinstance(shipment, ShipmentOut):
            fields.append('cost_method')
        return fields

    @property
    def shipment_cost_amount(self):
        cost = Decimal(0)
        for line in self.lines:
            if line.type == 'line' and line.shipment_cost is not None:
                cost += line.amount
        return cost

    def _get_shipment_sale(self, Shipment, key):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        shipment = super()._get_shipment_sale(Shipment, key)
        if isinstance(shipment, ShipmentOut):
            shipment.cost_method = self.shipment_cost_method
            shipment.carrier = self.carrier
        return shipment


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'
    shipment_cost = fields.Numeric('Shipment Cost', digits=price_digits)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        # shipment_cost is needed to compute the unit_price
        cls.unit_price.depends.add('shipment_cost')

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)

        super().__register__(module)

        # Migration from 6.4: drop shipment cost unique
        table_h.drop_constraint('sale_shipment_cost_unique')

    @fields.depends('shipment_cost', 'unit_price')
    def compute_unit_price(self):
        unit_price = super().compute_unit_price()
        if self.shipment_cost is not None:
            unit_price = self.unit_price
        return unit_price

    def get_invoice_line(self):
        context = Transaction().context
        shipment_cost_invoiced = context.get('_shipment_cost_invoiced')
        lines = super().get_invoice_line()
        if (self.shipment_cost is not None
                and shipment_cost_invoiced is not None):
            for shipment in self.sale.shipments:
                if (shipment.state == 'done'
                        and shipment.id not in shipment_cost_invoiced):
                    invoice_line = shipment.get_cost_invoice_line(
                        self.sale._get_invoice_sale(), origin=self)
                    if invoice_line:
                        lines.append(invoice_line)
                        shipment_cost_invoiced.append(shipment.id)
        return lines

    def _get_invoice_line_quantity(self):
        quantity = super()._get_invoice_line_quantity()
        if self.shipment_cost is not None:
            if self.sale.shipment_cost_method == 'shipment':
                quantity = 0
            elif (self.sale.shipment_cost_method == 'order'
                    and self.sale.invoice_method == 'shipment'):
                shipments = self.sale.shipments
                if (not shipments
                        or all(s.state != 'done' for s in shipments)):
                    quantity = 0
        return quantity

    def _get_invoiced_quantity(self):
        quantity = super()._get_invoiced_quantity()
        if self.shipment_cost is not None:
            if self.sale.shipment_cost_method == 'shipment':
                quantity = 0
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
                if line.shipment_cost is not None:
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
            })

    @classmethod
    def default_amount_shipment_cost_included(cls):
        return False

    def get_context_formula(self, sale_line):
        context = super(Promotion, self).get_context_formula(sale_line)
        if sale_line and sale_line.shipment_cost is not None:
            context['names']['unit_price'] = sale_line.shipment_cost
        return context

    def get_sale_amount(self, sale):
        amount = super().get_sale_amount(sale)
        if not self.amount_shipment_cost_included:
            amount -= sum(
                l.amount for l in sale.lines if l.shipment_cost is not None)
            if not self.untaxed_amount:
                amount -= sum(
                    v['amount']
                    for l in sale.lines if l.shipment_cost is not None
                    for v in l._get_taxes().values())
        return amount
