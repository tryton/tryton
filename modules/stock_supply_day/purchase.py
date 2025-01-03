# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'
    weekdays = fields.Many2Many(
        'purchase.product_supplier.day', 'product_supplier', 'day',
        "Week Days")

    def compute_supply_date(self, date=None):
        date = super().compute_supply_date(date=date)
        earlier_date = None
        if date != datetime.date.max:
            for weekday in self.weekdays:
                diff = weekday.index - date.weekday()
                if diff < 0:
                    diff += 7
                new_date = date + datetime.timedelta(diff)

                if earlier_date and earlier_date <= new_date:
                    continue
                earlier_date = new_date
        return earlier_date or date

    def compute_purchase_date(self, date):
        later_date = None
        for weekday in self.weekdays:
            diff = (date.weekday() - weekday.index) % 7
            new_date = date - datetime.timedelta(diff)
            if later_date and later_date >= new_date:
                continue
            later_date = new_date
        if later_date:
            date = later_date
        return super().compute_purchase_date(date)


class ProductSupplierDay(ModelSQL):
    __name__ = 'purchase.product_supplier.day'
    product_supplier = fields.Many2One(
        'purchase.product_supplier', 'Supplier',
        required=True, ondelete='CASCADE')
    day = fields.Many2One('ir.calendar.day', "Day", required=True)
