# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.config import config

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
    'Employee Cost Price'
    __name__ = 'company.employee_cost_price'
    date = fields.Date('Date', required=True, select=True)
    cost_price = fields.Numeric('Cost Price',
        digits=price_digits, required=True, help="Hourly cost price.")
    employee = fields.Many2One('company.employee', 'Employee')

    @classmethod
    def __setup__(cls):
        super(EmployeeCostPrice, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('employee_date_cost_price_uniq',
                Unique(t, t.employee, t.date, t.cost_price),
                'timesheet_cost.msg_employee_unique_cost_price_date'),
            ]
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
    def delete(cls, prices):
        Employee = Pool().get('company.employee')
        super(EmployeeCostPrice, cls).delete(prices)
        Employee._cost_prices_cache.clear()

    @classmethod
    def create(cls, vlist):
        Employee = Pool().get('company.employee')
        prices = super(EmployeeCostPrice, cls).create(vlist)
        Employee._cost_prices_cache.clear()
        return prices

    @classmethod
    def write(cls, *args):
        Employee = Pool().get('company.employee')
        super(EmployeeCostPrice, cls).write(*args)
        Employee._cost_prices_cache.clear()
