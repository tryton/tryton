# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.model import fields

from .company import price_digits


class Line(metaclass=PoolMeta):
    __name__ = 'timesheet.line'

    cost_price = fields.Numeric('Cost Price',
        digits=price_digits, required=True, readonly=True)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Employee = pool.get('company.employee')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        table_h = cls.__table_handler__(module_name)

        migrate_cost_price = not table_h.column_exist('cost_price')

        super().__register__(module_name)

        # Migration from 3.6: add cost_price
        if migrate_cost_price:
            cursor.execute(*table.select(table.id, table.employee, table.date,
                    where=(table.cost_price == 0)
                    & (table.employee != Null)
                    & (table.date != Null)))
            for line_id, employee_id, date in cursor.fetchall():
                employee = Employee(employee_id)
                cost_price = employee.compute_cost_price(date=date)
                cursor.execute(*table.update(
                        [table.cost_price],
                        [cost_price],
                        where=table.id == line_id))

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
    def sync_cost(cls, lines):
        with Transaction().set_context(_check_access=False):
            to_write = []
            lines = cls.browse(lines)
            for line in lines:
                cost_price = line.employee.compute_cost_price(date=line.date)
                if cost_price != line.cost_price:
                    to_write.extend([[line], {'cost_price': cost_price}])
            if to_write:
                cls.write(*to_write)
