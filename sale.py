# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def _get_carrier_selection_pattern(self):
        pattern = super()._get_carrier_selection_pattern()

        def parents(subdivision):
            while subdivision:
                yield subdivision
                subdivision = subdivision.parent

        pattern['from_subdivision'] = None
        if self.warehouse and self.warehouse.address:
            address = self.warehouse.address
            if address.subdivision:
                pattern['from_subdivision'] = address.subdivision.id
            if address.zip:
                pattern['from_zip'] = address.zip
        pattern['to_subdivision'] = None
        if self.shipment_address:
            address = self.shipment_address
            if address.subdivision:
                pattern['to_subdivision'] = address.subdivision.id
            if address.zip:
                pattern['to_zip'] = address.zip
        return pattern
