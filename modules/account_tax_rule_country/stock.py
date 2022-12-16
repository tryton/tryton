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

        from_country, to_country = None, None
        if self.from_location.warehouse:
            if self.from_location.warehouse.address:
                from_country = self.from_location.warehouse.address.country
        elif isinstance(self.origin, ShipmentOutReturn):
            from_country = self.origin.delivery_address.country
        if self.to_location.warehouse:
            if self.to_location.warehouse.address:
                to_country = self.to_location.warehouse.address.country
        elif isinstance(self.origin, ShipmentOut):
            to_country = self.origin.delivery_address.country

        pattern['from_country'] = from_country.id if from_country else None
        pattern['to_country'] = to_country.id if to_country else None
        return pattern
