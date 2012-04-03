#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from trytond.model import ModelView, ModelSQL, fields


class ProductSupplier(ModelSQL, ModelView):
    _name = 'purchase.product_supplier'
    weekdays = fields.One2Many('purchase.product_supplier.day',
        'product_supplier', 'Week Days')

    def compute_supply_date(self, product_supplier, date=None):
        date = super(ProductSupplier, self).compute_supply_date(
                product_supplier, date=date)
        earlier_date = None
        for day in product_supplier.weekdays:
            weekday = int(day.weekday)
            diff = weekday - date.weekday()
            if diff < 0:
                diff += 7
            new_date = date + datetime.timedelta(diff)

            if earlier_date and earlier_date <= new_date:
                continue
            earlier_date = new_date
        return earlier_date

    def compute_purchase_date(self, product_supplier, date):
        later_date = None
        for day in product_supplier.weekdays:
            weekday = int(day.weekday)
            diff = (date.weekday() - weekday) % 7
            new_date = date - datetime.timedelta(diff)
            if later_date and later_date >= new_date:
                continue
            later_date = new_date
        if later_date:
            date = later_date
        return super(ProductSupplier, self).compute_purchase_date(
                product_supplier, date)

ProductSupplier()


class ProductSupplierDay(ModelSQL, ModelView):
    'Product Supplier Day'
    _name = 'purchase.product_supplier.day'
    _rec_name = 'weekday'
    _description = __doc__

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

    def __init__(self):
        super(ProductSupplierDay, self).__init__()
        self._order.insert(0, ('weekday', 'ASC'))

    def default_weekday(self):
        return '0'

ProductSupplierDay()
