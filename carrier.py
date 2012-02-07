#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields


class Carrier(Model):
    _name = 'carrier'

    carrier_cost_allocation_method = fields.Selection([
            ('value', 'By Value'),
            ], 'Carrier Cost Allocation Method', required=True)

    def default_carrier_cost_allocation_method(self):
        return 'value'

Carrier()
