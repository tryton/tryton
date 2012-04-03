#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.cacheable import Cacheable
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class Employee(ModelSQL, ModelView, Cacheable):
    _name = 'company.employee'

    cost_price = fields.Function(fields.Numeric('Cost Price',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        help="Hourly cost price for this Employee"), 'get_cost_price')
    cost_prices = fields.One2Many('company.employee_cost_price', 'employee',
            'Cost Prices', help="List of hourly cost price over time")
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'get_currency_digits')

    def get_cost_price(self, ids, name):
        '''
        Return the cost price at the date given in the context or the
        current date
        '''

        res = {}
        ctx_date = Transaction().context.get('date', None)

        for employee_id in ids:
            res[employee_id] = self.compute_cost_price(employee_id, ctx_date)
        return res

    def compute_cost_price(self, employee_id, date=None):
        date_obj = Pool().get('ir.date')
        cost_price_obj = Pool().get('company.employee_cost_price')

        # Get from cache employee costs or fetch them from the db
        employee_costs = self.get(employee_id)
        if employee_costs is None:
            cost_price_ids = cost_price_obj.search([
                    ('employee', '=', employee_id),
                    ], order=[('date', 'ASC')])
            cost_prices = cost_price_obj.browse(cost_price_ids)

            employee_costs = []
            for cost_price in cost_prices:
                employee_costs.append(
                    (cost_price.date, cost_price.cost_price))
            self.add(employee_id, employee_costs)

        if date is None:
            date = date_obj.today()
        # compute the cost price for the given date
        cost = 0
        if employee_costs and date >= employee_costs[0][0]:
            for edate, ecost in employee_costs:
                if date >= edate:
                    cost = ecost
                    break
        return cost

    def get_currency_digits(self, ids, name):
        res = {}
        for employee in self.browse(ids):
            res[employee.id] = employee.company.currency.digits
        return res

    def on_change_with_currency_digits(self, vals):
        company_obj = Pool().get('company.company')
        if vals.get('company'):
            company = company_obj.browse(vals['company'])
            return company.currency.digits
        return 2

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.digits
        return 2

Employee()


class EmployeeCostPrice(ModelSQL, ModelView):
    'Employee Cost Price'
    _name = 'company.employee_cost_price'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=True)
    cost_price = fields.Numeric('Cost Price',
            digits=(16, Eval('currency_digits', 2)),
            required=True, depends=['currency_digits'],
            help="Hourly cost price")
    employee = fields.Many2One('company.employee', 'Employee')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['employee']), 'get_currency_digits')

    def __init__(self):
        super(EmployeeCostPrice, self).__init__()
        self._sql_constraints = [
            ('date_cost_price_uniq', 'UNIQUE(date, cost_price)',
                'A employee can only have one cost price by date!'),
        ]
        self._order.insert(0, ('date', 'DESC'))

    def default_cost_price(self):
        return Decimal(0)

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def delete(self, ids):
        Pool().get('company.employee').clear()
        return super(EmployeeCostPrice, self).delete(ids)

    def create(self, vals):
        Pool().get('company.employee').clear()
        return super(EmployeeCostPrice, self).create(vals)

    def write(self, ids, vals):
        Pool().get('company.employee').clear()
        return super(EmployeeCostPrice, self).write(ids, vals)

    def get_currency_digits(self, ids, name):
        res = {}
        for costprice in self.browse(ids):
            res[costprice.id] = costprice.employee.company.currency.digits
        return res

    def on_change_with_currency_digits(self, vals):
        employee_obj = Pool().get('company.employee')
        if vals.get('employee'):
            employee = employee_obj.browse(vals['employee'])
            return employee.company.currency.digits
        return 2

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.digits
        return 2

EmployeeCostPrice()
