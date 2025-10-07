# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

import trytond.config as config
from trytond.cache import Cache
from trytond.model import Index, ModelSQL, ModelView, Unique, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['price_digits']

price_digits = (16, config.getint(
        'timesheet_cost', 'price_decimal', default=4))


class Employee(metaclass=PoolMeta):
    __name__ = 'company.employee'
    cost_price = fields.Function(fields.Numeric('Cost Price',
            digits=price_digits,
            help="Hourly cost price for this Employee."), 'get_cost_price')
    cost_prices = fields.One2Many('company.employee_cost_price', 'employee',
            'Cost Prices', help="List of hourly cost price over time.")
    _cost_prices_cache = Cache('company_employee.cost_prices')

    def get_cost_price(self, name):
        '''
        Return the cost price at the date given in the context or the
        current date
        '''
        ctx_date = Transaction().context.get('date', None)
        return self.compute_cost_price(ctx_date)

    def get_employee_costs(self):
        "Return a sorted list by date of start date and cost_price"
        pool = Pool()
        CostPrice = pool.get('company.employee_cost_price')
        # Get from cache employee costs or fetch them from the db
        employee_costs = self._cost_prices_cache.get(self.id)
        if employee_costs is None:
            cost_prices = CostPrice.search([
                    ('employee', '=', self.id),
                    ], order=[('date', 'ASC')])

            employee_costs = []
            for cost_price in cost_prices:
                employee_costs.append(
                    (cost_price.date, cost_price.cost_price))
            self._cost_prices_cache.set(self.id, employee_costs)
        return employee_costs

    def compute_cost_price(self, date=None):
        "Return the cost price at the given date"
        pool = Pool()
        Date = pool.get('ir.date')

        employee_costs = self.get_employee_costs()

        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        # compute the cost price for the given date
        cost = 0
        if employee_costs and date >= employee_costs[0][0]:
            for edate, ecost in employee_costs:
                if date >= edate:
                    cost = ecost
                else:
                    break
        return cost


class EmployeeCostPrice(ModelSQL, ModelView):
    __name__ = 'company.employee_cost_price'
    date = fields.Date("Date", required=True)
    cost_price = fields.Numeric('Cost Price',
        digits=price_digits, required=True, help="Hourly cost price.")
    employee = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('employee_date_cost_price_uniq',
                Unique(t, t.employee, t.date, t.cost_price),
                'timesheet_cost.msg_employee_unique_cost_price_date'),
            ]
        cls._sql_indexes.add(
            Index(
                t,
                (t.employee, Index.Range()),
                (t.date, Index.Range(order='ASC'))))
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def default_cost_price():
        return Decimal(0)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    def get_rec_name(self, name):
        return str(self.date)

    @classmethod
    def on_modification(cls, mode, prices, field_names=None):
        pool = Pool()
        Employee = pool.get('company.employee')
        super().on_modification(mode, prices, field_names=field_names)
        Employee._cost_prices_cache.clear()
