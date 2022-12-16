# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'
    weekdays = fields.Many2Many(
        'purchase.product_supplier.day', 'product_supplier', 'day',
        "Week Days")

    def compute_supply_date(self, date=None):
        date = super(ProductSupplier, self).compute_supply_date(date=date)
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
        return super(ProductSupplier, self).compute_purchase_date(date)


class ProductSupplierDay(ModelSQL):
    'Product Supplier Day'
    __name__ = 'purchase.product_supplier.day'
    product_supplier = fields.Many2One(
        'purchase.product_supplier', 'Supplier',
        required=True, ondelete='CASCADE', select=True)
    day = fields.Many2One('ir.calendar.day', "Day", required=True)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Day = pool.get('ir.calendar.day')
        day = Day.__table__()
        transaction = Transaction()
        table = cls.__table__()

        super().__register__(module_name)
        table_h = cls.__table_handler__(module_name)

        # Migration from 5.0: replace weekday by day
        if table_h.column_exist('weekday'):
            cursor = transaction.connection.cursor()
            update = transaction.connection.cursor()
            cursor.execute(*day.select(day.id, day.index))
            for day_id, index in cursor:
                update.execute(*table.update(
                        [table.day], [day_id],
                        where=table.weekday == str(index)))
            table_h.drop_column('weekday')
