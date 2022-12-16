# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @fields.depends('warehouse', 'shipment_address')
    def _get_carrier_selection_pattern(self):
        pattern = super()._get_carrier_selection_pattern()
        pattern['from_subdivision'] = None
        if self.warehouse and self.warehouse.address:
            address = self.warehouse.address
            if address.subdivision:
                pattern['from_subdivision'] = address.subdivision.id
            if address.postal_code:
                pattern['from_postal_code'] = address.postal_code
        pattern['to_subdivision'] = None
        if self.shipment_address:
            address = self.shipment_address
            if address.subdivision:
                pattern['to_subdivision'] = address.subdivision.id
            if address.postal_code:
                pattern['to_postal_code'] = address.postal_code
        return pattern


class Carriage(metaclass=PoolMeta):
    __name__ = 'sale.carriage'

    @fields.depends('from_', 'to')
    def _get_carrier_selection_pattern(self):
        pattern = super()._get_carrier_selection_pattern()
        pattern['from_subdivision'] = None
        if self.from_:
            if self.from_.subdivision:
                pattern['from_subdivision'] = self.from_.subdivision.id
            if self.from_.postal_code:
                pattern['from_postal_code'] = self.from_.postal_code
        pattern['to_subdivision'] = None
        if self.to:
            if self.to.subdivision:
                pattern['to_subdivision'] = self.to.subdivision.id
            if self.to.postal_code:
                pattern['to_postal_code'] = self.to.postal_code
        return pattern
