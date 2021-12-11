# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.sale.party import get_sale_methods
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


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
    def copy(cls, parties, default=None):
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
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
