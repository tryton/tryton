#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.osv import OSV, fields
import datetime


class ProductSupplier(OSV):
    _name = 'purchase.product_supplier'

    weekday = fields.Selection([
        ('-1', ''),
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
        ], 'Week Day', required=True, sort=False)

    def default_weekday(self, cursor, user, context=None):
        return -1

    def compute_supply_date(self, cursor, user, product_supplier, date=None,
            context=None):
        res = super(ProductSupplier, self).compute_supply_date(cursor, user,
                product_supplier, date=date, context=context)
        weekday = int(product_supplier.weekday)
        if  weekday >= 0:
            date = res[0]
            next_date = res[1]
            diff = weekday - date.weekday()
            if diff < 0:
                diff += 7
            date = date + datetime.timedelta(diff)

            diff = weekday - next_date.weekday()
            if diff < 0:
                diff += 7
            next_date = next_date + datetime.timedelta(diff)
            res = (date, next_date)
        return res

    def compute_purchase_date(self, cursor, user, product_supplier, date,
            context=None):
        weekday = int(product_supplier.weekday)
        if weekday >= 0:
            diff = date.weekday() - weekday
            if diff > 0:
                diff -= 7
            date = date + datetime.timedelta(diff)
        return super(ProductSupplier, self).compute_purchase_date(cursor, user,
                product_supplier, date, context=context)

ProductSupplier()
