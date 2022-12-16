#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Employee', 'EmployeeCostPrice']
__metaclass__ = PoolMeta


class Employee:
    __name__ = 'company.employee'
    cost_price = fields.Function(fields.Numeric('Cost Price',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        help="Hourly cost price for this Employee"), 'get_cost_price')
    cost_prices = fields.One2Many('company.employee_cost_price', 'employee',
            'Cost Prices', help="List of hourly cost price over time")
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['company']), 'on_change_with_currency_digits')
    _cost_prices_cache = Cache('company_employee.cost_prices')

    def get_cost_price(self, name):
        '''
        Return the cost price at the date given in the context or the
        current date
        '''
        ctx_date = Transaction().context.get('date', None)
        return self.compute_cost_price(ctx_date)

    def compute_cost_price(self, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
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


class EmployeeCostPrice(ModelSQL, ModelView):
    'Employee Cost Price'
    __name__ = 'company.employee_cost_price'
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=True)
    cost_price = fields.Numeric('Cost Price',
            digits=(16, Eval('currency_digits', 2)),
            required=True, depends=['currency_digits'],
            help="Hourly cost price")
    employee = fields.Many2One('company.employee', 'Employee')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['employee']), 'on_change_with_currency_digits')

    @classmethod
    def __setup__(cls):
        super(EmployeeCostPrice, cls).__setup__()
        cls._sql_constraints = [
            ('date_cost_price_uniq', 'UNIQUE(date, cost_price)',
                'A employee can only have one cost price by date.'),
            ]
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def default_cost_price():
        return Decimal(0)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

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
    def write(cls, prices, vals):
        Employee = Pool().get('company.employee')
        super(EmployeeCostPrice, cls).write(prices, vals)
        Employee._cost_prices_cache.clear()

    def on_change_with_currency_digits(self, name=None):
        if self.employee:
            return self.employee.company.currency.digits
        return 2

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2
