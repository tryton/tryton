#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Service"
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.cacheable import Cacheable


class Employee(ModelSQL, ModelView, Cacheable):
    _name = 'company.employee'

    cost_price = fields.Function('get_cost_price', string='Cost Price',
            digits=(12, 6), help="Hourly cost price for this Employee")
    cost_prices = fields.One2Many('company.employee_cost_price', 'employee',
            'Cost Prices', help="List of hourly cost price over time")

    def get_cost_price(self, cursor, user, ids, name, arg, context=None):
        '''
        Return the cost price at the date given in the context or the
        current date
        '''
        cost_price_obj = self.pool.get('company.employee_cost_price')
        date_obj = self.pool.get('ir.date')

        res = {}
        if context is None:
            context = {}
        ctx_date = context.get('date', date_obj.today(cursor, user,
            context=context))

        # construct employee_costs which map an employee_id to an
        # ordered list of (date, cost) and  cache results.
        to_fetch = []
        employee_costs = {}
        for employee_id in ids:
            if self.get(cursor, employee_id) is None:
                to_fetch.append(employee_id)
                employee_costs[employee_id] = []
            else:
               employee_costs[employee_id] = self.get(cursor, employee_id)

        cost_price_ids = cost_price_obj.search(cursor, user, [
                ('employee', 'in', to_fetch),
                ], order=[('date', 'ASC')])
        cost_prices = cost_price_obj.browse(
            cursor, user, cost_price_ids, context=context)

        for cost_price in cost_prices:
            employee_costs[cost_price.employee.id].append(
                (cost_price.date, cost_price.cost_price))

        for employee_id in to_fetch:
            if employee_id in employee_costs:
                self.add(cursor, employee_id, employee_costs[employee_id])

        # compute the cost price for each employee at the given date
        res = {}
        for employee_id in ids:
            if employee_id not in employee_costs:
                res[employee_id] = 0
                continue
            if ctx_date < employee_costs[employee_id][0][0]:
                res[employee_id] = 0
                continue
            for date, cost in employee_costs[employee_id]:
                if date <= ctx_date:
                    res[employee_id] = cost

        return res

Employee()


class EmployeeCostPrice(ModelSQL, ModelView):
    'Employee Cost Price'
    _name = 'company.employee_cost_price'
    _description = __doc__
    _rec_name = 'date'
    date = fields.Date('Date', required=True, select=1)
    cost_price = fields.Numeric('Cost Price', digits=(12, 6), required=True,
            help="Hourly cost price")
    employee = fields.Many2One('company.employee', 'Employee')

    def __init__(self):
        super(EmployeeCostPrice, self).__init__()
        self._sql_constraints = [
            ('date_cost_price_uniq', 'UNIQUE(date, cost_price)',
                'A employee can only have one cost price by date!'),
        ]
        self._order.insert(0, ('date', 'DESC'))

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def delete(self, cursor, user, ids, context=None):
        self.pool.get('company.employee').clear(cursor)
        return super(EmployeeCostPrice , self).delete(cursor, user, ids,
                context=context)

    def create(self, cursor, user, vals, context=None):
        self.pool.get('company.employee').clear(cursor)
        return super(EmployeeCostPrice , self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        self.pool.get('company.employee').clear(cursor)
        return super(EmployeeCostPrice , self).write(cursor, user, ids, vals,
                context=context)

EmployeeCostPrice()
