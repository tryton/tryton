# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import without_check_access

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
    def create(cls, vlist):
        # XXX Remove cost_price because proteus set it as default value
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            values.pop('cost_price', None)
        lines = super().create(vlist)
        cls.sync_cost(lines)
        return lines

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls.sync_cost(sum(args[0:None:2], []))

    @classmethod
    @without_check_access
    def sync_cost(cls, lines):
        to_write = []
        lines = cls.browse(lines)
        for line in lines:
            cost_price = line.employee.compute_cost_price(date=line.date)
            if cost_price != line.cost_price:
                to_write.extend([[line], {'cost_price': cost_price}])
        if to_write:
            cls.write(*to_write)
