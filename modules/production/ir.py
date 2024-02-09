# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('production|set_cost_from_moves', "Set Cost from Moves"),
                ('production|reschedule', "Reschedule Productions"),
                ])

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        super().__register__(module)

        # Migration from 7.0: replace assign_cron
        cursor.execute(*table.update(
                [table.method], ['ir.cron|stock_shipment_assign_try'],
                where=table.method == 'production|assign_cron'))
