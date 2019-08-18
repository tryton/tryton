# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _get_tax_rule_pattern(self):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        pattern = super(Move, self)._get_tax_rule_pattern()

        from_country = from_subdivision = to_country = to_subdivision = None
        if self.from_location.warehouse:
            warehouse_address = self.from_location.warehouse.address
            if warehouse_address:
                from_country = warehouse_address.country
                from_subdivision = warehouse_address.subdivision
        elif isinstance(self.origin, ShipmentOutReturn):
            delivery_address = self.origin.delivery_address
            from_country = delivery_address.country
            from_subdivision = delivery_address.subdivision
        if self.to_location.warehouse:
            warehouse_address = self.to_location.warehouse.address
            if warehouse_address:
                to_country = warehouse_address.country
                to_subdivision = warehouse_address.subdivision
        elif isinstance(self.origin, ShipmentOut):
            delivery_address = self.origin.delivery_address
            to_country = delivery_address.country
            to_subdivision = delivery_address.subdivision

        pattern['from_country'] = from_country.id if from_country else None
        pattern['from_subdivision'] = (
            from_subdivision.id if from_subdivision else None)
        pattern['to_country'] = to_country.id if to_country else None
        pattern['to_subdivision'] = (
            to_subdivision.id if to_subdivision else None)
        return pattern
