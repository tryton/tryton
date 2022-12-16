# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipment_cost_allocation_method.selection.append(
            ('weight', "By Weight"))
