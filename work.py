# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime

from trytond.model import fields
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids, grouped_slice

__all__ = ['Work']
__metaclass__ = PoolMeta


class Work:
    __name__ = 'project.work'
    product = fields.Many2One('product.product', 'Product',
        domain=[
            ('type', '=', 'service'),
            ('default_uom_category', '=', Id('product', 'uom_cat_time')),
            ])
    list_price = fields.Numeric('List Price',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    revenue = fields.Function(fields.Numeric('Revenue',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_revenue')
    cost = fields.Function(fields.Numeric('Cost',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_cost')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')

    @classmethod
    def get_cost(cls, works, name):
        pool = Pool()
        Employee = pool.get('company.employee')
        Line = pool.get('timesheet.line')
        Work = pool.get('timesheet.work')
        transaction = Transaction()
        cursor = transaction.cursor

        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])
        costs = dict.fromkeys([w.id for w in works], 0)

        table = cls.__table__()
        table_c = cls.__table__()
        work = Work.__table__()
        line = Line.__table__()

        work_ids = [w.id for w in works]
        employee_ids = set()
        for sub_ids in grouped_slice(work_ids):
            red_sql = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(table_c,
                    condition=(table_c.left >= table.left)
                    & (table_c.right <= table.right)
                    ).join(work,
                    condition=table_c.work == work.id
                    ).join(line, condition=line.work == work.id
                    ).select(line.employee,
                    where=red_sql,
                    group_by=line.employee))
            employee_ids |= set(r[0] for r in cursor.fetchall())
        for employee in Employee.browse(list(employee_ids)):
            employee_costs = employee.get_employee_costs()
            to_date = None
            for from_date, cost in reversed(employee_costs):
                with transaction.set_context(
                        from_date=from_date,
                        to_date=to_date,
                        employees=[employee.id]):
                    for work in cls.browse(work_ids):
                        costs[work.id] += (
                            Decimal(str(work.timesheet_duration_hours)) * cost)
                to_date = from_date - datetime.timedelta(1)
        for work in works:
            costs[work.id] = work.company.currency.round(costs[work.id])
        return costs

    @classmethod
    def get_revenue(cls, works, name):
        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])

        def getter(work):
            if work.list_price:
                return work.list_price * Decimal(str(work.effort_hours))
            else:
                return Decimal(0)

        return cls.sum_tree(works, getter)

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('product', 'party', 'company')
    def on_change_product(self):
        pool = Pool()
        User = pool.get('res.user')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        if not self.product:
            return

        context = {}

        if self.party:
            context['customer'] = self.party.id

        hour_uom = Uom(ModelData.get_id('product', 'uom_hour'))

        with Transaction().set_context(context):
            self.list_price = Uom.compute_price(self.product.default_uom,
                self.product.list_price, hour_uom)

        if self.company:
            user = User(Transaction().user)
            if user.company != self.company:
                if user.company.currency != self.company.currency:
                    self.list_price = Currency.compute(user.company.currency,
                        self.list_price, self.company.currency)
