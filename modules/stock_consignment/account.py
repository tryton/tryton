# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @property
    def origin_name(self):
        pool = Pool()
        Move = pool.get('stock.move')
        name = super(InvoiceLine, self).origin_name
        if (isinstance(self.origin, Move)
                and self.origin.shipment):
            name = self.origin.shipment.rec_name
        return name

    @classmethod
    def _get_origin(cls):
        return super(InvoiceLine, cls)._get_origin() + ['stock.move']
