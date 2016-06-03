# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Sale', 'SaleLine']


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        for field in (cls.shipment_party, cls.shipment_address, cls.warehouse):
            field.states['readonly'] |= (
                Eval('lines', [0]) & Eval('shipment_address'))
            field.depends.extend(['shipment_address'])


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    def _get_tax_rule_pattern(self):
        pool = Pool()
        Location = pool.get('stock.location')

        pattern = super(SaleLine, self)._get_tax_rule_pattern()

        from_country, to_country = None, None
        if self.id is None or self.id < 0:
            warehouse = self.get_warehouse('warehouse')
            if warehouse:
                warehouse = Location(warehouse)
        else:
            warehouse = self.warehouse
        if warehouse and warehouse.address:
            from_country = warehouse.address.country
        if self.sale and self.sale.shipment_address:
            to_country = self.sale.shipment_address.country

        pattern['from_country'] = from_country.id if from_country else None
        pattern['to_country'] = to_country.id if to_country else None
        return pattern

    @fields.depends('_parent_sale.warehouse', '_parent_sale.shipment_address')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
