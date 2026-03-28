# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

from .party import IDENTIFIER_TYPES


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    warehouse_eu_excise_number = fields.Function(
        fields.Many2One('party.identifier', "Warehouse Excise Number"),
        'on_change_with_warehouse_eu_excise_number')
    eu_excise_number = fields.Many2One(
        'party.identifier', "Excise Number",
        domain=[
            ('type', 'in', Eval('eu_excise_types', [])),
            ('party', '=', If(Eval('shipment_party', -1),
                    Eval('shipment_party', -1),
                    Eval('party', -1))),
            ('address', '=', Eval('shipment_address', -1)),
            ],
        states={
            'invisible': ~Eval('warehouse_eu_excise_number'),
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            })
    eu_excise_types = fields.Function(
        fields.MultiSelection(IDENTIFIER_TYPES, "Excise Types"),
        'on_change_with_eu_excise_types')
    eu_excise_duty_amount = fields.Function(Monetary(
            "Excise Duty Amount", digits='currency', currency='currency'),
        'get_eu_excise_duty_amount')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.warehouse.states['readonly'] = (
            cls.warehouse.states.get('readonly', False)
            | Eval('eu_excise_number'))

    @fields.depends(methods=['_clear_eu_excise_number'])
    def on_change_party(self):
        try:
            super().on_change_party()
        except AttributeError:
            pass
        self._clear_eu_excise_number()

    @fields.depends(methods=['_clear_eu_excise_number'])
    def on_change_shipment_party(self):
        try:
            super().on_change_shipment_party()
        except AttributeError:
            pass
        self._clear_eu_excise_number()

    @fields.depends('party', 'shipment_party', 'eu_excise_number')
    def _clear_eu_excise_number(self):
        if (self.eu_excise_number
            and self.eu_excise_number.party != (
                    self.shipment_party or self.party)):
            self.eu_excise_number = None

    @fields.depends('warehouse', 'company')
    def on_change_with_warehouse_eu_excise_number(self, name=None):
        if self.warehouse:
            return self.warehouse.get_eu_excise_number(self.company)

    @fields.depends('warehouse_eu_excise_number')
    def on_change_with_eu_excise_types(self, name=None):
        types = set()
        if self.warehouse_eu_excise_number:
            types.add('eu_excise')
            types.add(self.warehouse_eu_excise_number.type)
        return list(types)

    def get_eu_excise_duty_amount(self, name):
        return sum(
            (l.eu_excise_duty_amount for l in self.lines
                if l.eu_excise_duty_amount is not None),
            Decimal(0))

    def _get_shipment_sale(self, Shipment, key):
        shipment = super()._get_shipment_sale(Shipment, key)
        shipment.eu_excise_number = self.eu_excise_number
        return shipment

    def _get_shipment_grouping_fields(self, shipment):
        return super()._get_shipment_grouping_fields(shipment) | {
            'eu_excise_number'}


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    eu_excise_duty_amount = fields.Function(Monetary(
            "Excise Duty Amount", digits='currency', currency='currency'),
        'get_eu_excise_duty_amount')

    def get_eu_excise_duty_amount(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        Currency = pool.get('currency.currency')

        amount = None
        if self.product and self.eu_excise_duty != 'suspension':
            country = None
            if (self.warehouse
                    and self.warehouse.address
                    and self.warehouse.address.country):
                country = self.warehouse.address.country
            if eu_excise_tax := self.product.get_eu_excise_tax(country):
                if not (date := self.sale.sale_date):
                    with Transaction().set_context(
                            company=self.sale.company.id):
                        date = Date.today()
                if tax_rate := eu_excise_tax.get_tax_rate({
                            'date': date,
                            }):
                    amount = tax_rate.compute(
                        self.product, self.quantity, self.unit)
                    if amount is not None:
                        with Transaction().set_context(date=date):
                            amount = Currency.compute(
                                eu_excise_tax.currency, amount, self.currency)
        return amount

    @property
    @fields.depends(
        'sale',
        '_parent_sale.warehouse',
        '_parent_sale.warehouse_eu_excise_number',
        '_parent_sale.eu_excise_number',
        'product')
    def eu_excise_duty(self):
        if (self.sale
                and self.sale.warehouse_eu_excise_number
                and self.sale.eu_excise_number
                and self.product):
            warehouse_eu_excise_number = self.sale.warehouse_eu_excise_number
            eu_excise_number = self.sale.eu_excise_number
            if (warehouse_eu_excise_number.is_excise_product(self.product)
                    and eu_excise_number.is_excise_product(self.product)):
                return 'suspension'

    @fields.depends(
        'sale', '_parent_sale.warehouse', 'product',
        methods=['eu_excise_duty'])
    def _get_context_sale_price(self):
        context = super()._get_context_sale_price()
        context['eu_excise_duty'] = self.eu_excise_duty
        country = None
        if (self.warehouse
                and self.warehouse.address
                and self.warehouse.address.country):
            country = self.warehouse.address.country
        if eu_excise_tax := self.product.get_eu_excise_tax(country):
            context['eu_excise_tax'] = eu_excise_tax.id
        return context
