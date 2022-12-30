# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


def get_sale_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get([field_name])[field_name]['selection'] + [
            ('default', "")]
    return func


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    sale_shipment_cost_method = fields.MultiValue(fields.Selection(
            'get_sale_shipment_cost_method', "Shipment Cost Method",
            help="The default shipment cost method for the customer.\n"
            "Leave empty to use the default value from the configuration."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_shipment_cost_method':
            return pool.get('party.party.sale_method')
        return super().multivalue_model(field)

    get_sale_shipment_cost_method = get_sale_methods('shipment_cost_method')

    @classmethod
    def default_sale_shipment_cost_method(cls, **pattern):
        return 'default'

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        if Transaction().check_access:
            fields = ['sale_shipment_cost_method']
            default_values = cls.default_get(fields, with_rec_name=False)
            for fname in fields:
                default.setdefault(fname, default_values.get(fname))
        return super().copy(parties, default=default)


class PartySaleMethod(metaclass=PoolMeta):
    __name__ = 'party.party.sale_method'

    sale_shipment_cost_method = fields.Selection(
        'get_sale_shipment_cost_method', "Sale Shipment Cost Method")

    get_sale_shipment_cost_method = get_sale_methods('shipment_cost_method')
