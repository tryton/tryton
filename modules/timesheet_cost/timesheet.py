# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta

from .company import price_digits


class Line(metaclass=PoolMeta):
    __name__ = 'timesheet.line'

    cost_price = fields.Numeric('Cost Price',
        digits=price_digits, required=True, readonly=True)

    @classmethod
    def default_cost_price(cls):
        # Needed at creation as cost_price is required
        return 0

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            # XXX Remove cost_price because proteus set it as default value
            values.pop('cost_price', None)
        return values

    def compute_fields(self, field_names=None):
        values = super().compute_fields(field_names=field_names)
        cost_price = self.employee.compute_cost_price(date=self.date)
        if getattr(self, 'cost_price', None) != cost_price:
            values['cost_price'] = cost_price
        return values
