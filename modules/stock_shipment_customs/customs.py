# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import namedtuple
from decimal import Decimal

from trytond.pool import Pool
from trytond.report import Report


class CommercialInvoice(Report):
    __name__ = 'customs.commercial_invoice'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['lines'] = cls.lines
        context['get_reason'] = cls.get_reason
        context['get_phone'] = cls.get_phone
        context['get_tariff_code'] = cls.get_tariff_code
        context['get_value'] = cls.get_value
        context['get_weight'] = cls.get_weight
        context['get_total_weight'] = cls.get_total_weight
        context['get_total_value'] = cls.get_total_value
        return context

    @classmethod
    def lines(cls, shipment):
        Line = namedtuple(
            'Line',
            ['product', 'price', 'currency', 'unit', 'quantity', 'weight'])
        for key, value in shipment.customs_products.items():
            yield Line(*key, **value)

    @classmethod
    def get_reason(cls, shipment):
        return {
            'stock.shipment.out': 'SALE',
            'stock.shipment.in.return': 'RETURN',
            }.get(shipment.__class__.__name__)

    @classmethod
    def get_phone(cls, address):
        if (address
                and (phone := address.contact_mechanism_get(
                        {'phone', 'mobile'}))):
            return phone.value

    @classmethod
    def get_tariff_code(cls, shipment, product):
        if tariff_code := product.get_tariff_code({
                    'date': shipment.effective_date or shipment.planned_date,
                    'country': shipment.customs_to_country,
                    }):
            return tariff_code.code

    @classmethod
    def get_value(cls, quantity, price, currency):
        return currency.round(price * Decimal(str(quantity)))

    @classmethod
    def get_weight(cls, product, weight):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        return kg.round(weight), None, kg

    @classmethod
    def get_total_value(cls, shipment):
        pool = Pool()
        Currency = pool.get('currency.currency')
        currency, = {m.currency for m in shipment.customs_moves}
        return currency.round(sum(
                Currency.compute(
                    curr, cls.get_value(v['quantity'], price, curr), currency,
                    round=False)
                for (product, price, curr, _), v in
                shipment.customs_products.items())), None, currency

    @classmethod
    def get_total_weight(cls, shipment):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        return (kg.round(sum(
                    v['weight'] for v in shipment.customs_products.values())),
            None, kg)
