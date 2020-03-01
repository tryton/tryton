# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'
    carrier_cost_allocation_method = fields.Selection([
            ('value', 'By Value'),
            ], 'Carrier Cost Allocation Method', required=True)

    @staticmethod
    def default_carrier_cost_allocation_method():
        return 'value'
