# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby
from operator import attrgetter

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from .shipment import ShipmentAssignMixin


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('product.product|recompute_cost_price_from_moves',
                    "Recompute Cost Price from Moves"),
                ('stock.shipment.out|reschedule',
                    "Reschedule Customer Shipments"),
                ('stock.shipment.in.return|reschedule',
                    "Reschedule Supplier Return Shipments"),
                ('stock.shipment.internal|reschedule',
                    "Reschedule Internal Shipments"),
                ('ir.cron|stock_shipment_assign_try', "Assign Shipments"),
                ])

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        super().__register__(module)

        # Migration from 7.0: replace assign_cron
        cursor.execute(*table.update(
                [table.method], ['ir.cron|stock_shipment_assign_try'],
                where=table.method.in_([
                        'stock.shipment.out|assign_cron',
                        'stock.shipment.internal|assign_cron',
                        ])))

    @classmethod
    def stock_shipment_assign_try(cls):
        pool = Pool()
        records = []
        for _, kls in pool.iterobject():
            if issubclass(kls, ShipmentAssignMixin):
                records.extend(kls.to_assign())

        records.sort(key=attrgetter('assign_order_key'))

        for kls, records in groupby(records, key=attrgetter('__class__')):
            kls.assign_try(list(records))
