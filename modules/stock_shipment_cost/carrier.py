# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    shipment_cost_allocation_method = fields.Selection([
            ('cost', "By Cost"),
            ], "Allocation Method", required=True,
        help="Method to allocate shipment cost.")

    @classmethod
    def default_shipment_cost_allocation_method(cls):
        return 'cost'
