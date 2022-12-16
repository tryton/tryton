#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta

__all__ = ['ProductSupplier', 'ProductSupplierDay']
__metaclass__ = PoolMeta


class ProductSupplier:
    __name__ = 'purchase.product_supplier'
    weekdays = fields.One2Many('purchase.product_supplier.day',
        'product_supplier', 'Week Days')

    def compute_supply_date(self, date=None):
        date = super(ProductSupplier, self).compute_supply_date(date=date)
        earlier_date = None
        for day in self.weekdays:
            weekday = int(day.weekday)
            diff = weekday - date.weekday()
            if diff < 0:
                diff += 7
            new_date = date + datetime.timedelta(diff)

            if earlier_date and earlier_date <= new_date:
                continue
            earlier_date = new_date
        return earlier_date or date

    def compute_purchase_date(self, date):
        later_date = None
        for day in self.weekdays:
            weekday = int(day.weekday)
            diff = (date.weekday() - weekday) % 7
            new_date = date - datetime.timedelta(diff)
            if later_date and later_date >= new_date:
                continue
            later_date = new_date
        if later_date:
            date = later_date
        return super(ProductSupplier, self).compute_purchase_date(date)


class ProductSupplierDay(ModelSQL, ModelView):
    'Product Supplier Day'
    __name__ = 'purchase.product_supplier.day'
    _rec_name = 'weekday'
    product_supplier = fields.Many2One('purchase.product_supplier', 'Supplier',
            required=True, ondelete='CASCADE')
    weekday = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
        ], 'Week Day', required=True, sort=False)

    @classmethod
    def __setup__(cls):
        super(ProductSupplierDay, cls).__setup__()
        cls._order.insert(0, ('weekday', 'ASC'))

    @staticmethod
    def default_weekday():
        return '0'
