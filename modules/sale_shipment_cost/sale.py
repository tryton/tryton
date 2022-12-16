# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
        depends=['state', 'available_carriers'])
    available_carriers = fields.Function(
        fields.Many2Many('carrier', None, None, 'Available Carriers'),
        'on_change_with_available_carriers')
    shipment_cost_method = fields.Selection([
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
        ], 'Shipment Cost Method', required=True, states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])

    @staticmethod
    def default_shipment_cost_method():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_shipment_cost_method

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

    @fields.depends('warehouse', 'shipment_address')
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

    def set_shipment_cost(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Currency = pool.get('currency.currency')

        cost, currency_id = 0, None
        if (self.carrier
                and any(l.quantity >= 0 for l in self.lines
                    if l.type == 'line'
                    and l.product and l.product.type != 'service')):
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_sale_price()

        cost_line = None
        products = [line.product for line in self.lines or []
                if getattr(line, 'product', None)]
        stockable = any(product.type in ('goods', 'assets')
            for product in products)
        if cost and currency_id and stockable:
            today = Date.today()
            date = self.sale_date or today
            with Transaction().set_context(date=date):
                cost = Currency.compute(Currency(currency_id), cost,
                    self.currency, round=False)
            cost_line = self.get_shipment_cost_line(cost)

        removed = []
        lines = list(self.lines or [])
        for line in self.lines:
            if line.type == 'line' and line.shipment_cost:
                lines.remove(line)
                removed.append(line)
        if cost_line:
            lines.append(cost_line)
        self.lines = lines
        return removed

    def get_shipment_cost_line(self, cost):
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
        cost_line.unit_price = round_price(cost)
        cost_line.amount = cost_line.on_change_with_amount()
        return cost_line

    def create_shipment(self, shipment_type):
        Shipment = Pool().get('stock.shipment.out')

        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out' and shipments and self.carrier:
            for shipment in shipments:
                shipment.carrier = self.carrier
                with Transaction().set_context(
                        shipment.get_carrier_context()):
                    cost, currency_id = self.carrier.get_sale_price()
                cost = round_price(cost)
                Shipment.write([shipment], {
                        'carrier': self.carrier.id,
                        'cost': cost,
                        'cost_currency': currency_id,
                        })
        return shipments

    def create_invoice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Shipment = pool.get('stock.shipment.out')

        invoice = super(Sale, self).create_invoice()
        if invoice and self.shipment_cost_method == 'shipment':
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
            Invoice.update_taxes([invoice])
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

    def get_context_formula(self, sale_line):
        context = super(Promotion, self).get_context_formula(sale_line)
        if sale_line and sale_line.shipment_cost:
            context['names']['unit_price'] = sale_line.shipment_cost
        return context
