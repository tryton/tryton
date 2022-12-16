# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class UserCompany(ModelSQL):
    "User - Company"
    __name__ = 'res.user-company.company'

    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE', select=True, required=True)
    company = fields.Many2One(
        'company.company', "Company",
        ondelete='CASCADE', select=True, required=True)


class UserEmployee(ModelSQL):
    'User - Employee'
    __name__ = 'res.user-company.employee'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True, required=True)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    companies = fields.Many2Many(
        'res.user-company.company', 'user', 'company', "Companies",
        help="The companies that the user has access to.")
    company = fields.Many2One(
        'company.company', "Current Company",
        domain=[
            ('id', 'in', Eval('companies', [])),
            ],
        depends=['companies'],
        help="Select the company to work for.")
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees',
        domain=[
            ('company', 'in', Eval('companies', [])),
            ],
        depends=['companies'],
        help="Add employees to grant the user access to them.")
    employee = fields.Many2One('company.employee', 'Current Employee',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', 'in', Eval('employees', [])),
            ],
        depends=['company', 'employees'],
        help="Select the employee to make the user behave as such.")
    company_filter = fields.Selection([
            ('one', "Current"),
            ('all', "All"),
            ], "Company Filter",
        help="Define records of which companies are shown.")

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.insert(0, 'company')
        cls._context_fields.insert(0, 'employee')
        cls._context_fields.insert(0, 'company_filter')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        UserCompany = pool.get('res.user-company.company')
        transaction = Transaction()
        table = cls.__table__()
        user_company = UserCompany.__table__()

        super().__register__(module)

        table_h = cls.__table_handler__(module)
        cursor = transaction.connection.cursor()

        # Migration from 5.8: remove main_company
        if table_h.column_exist('main_company'):
            cursor.execute(*user_company.insert(
                    [user_company.user, user_company.company],
                    table.select(
                        table.id, table.main_company,
                        where=table.main_company != Null)))
            cursor.execute(*user_company.insert(
                    [user_company.user, user_company.company],
                    table.select(
                        table.id, table.company,
                        where=(table.company != Null)
                        & (table.company != table.main_company))))
            table_h.drop_column('main_company')

    @classmethod
    def default_companies(cls):
        company = Transaction().context.get('company')
        return [company] if company else []

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_company_filter(cls):
        return 'one'

    def get_status_bar(self, name):
        def same_company(record):
            return record.company == self.company
        status = super(User, self).get_status_bar(name)
        if (self.employee
                and len(list(filter(same_company, self.employees))) > 1):
            status += ' - %s' % self.employee.rec_name
        if self.company:
            if len(self.companies) > 1:
                status += ' - %s' % self.company.rec_name
            status += ' [%s]' % self.company.currency.code
        return status

    @fields.depends('company', 'employees')
    def on_change_company(self):
        Employee = Pool().get('company.employee')
        self.employee = None
        if self.company and self.employees:
            employees = Employee.search([
                    ('id', 'in', [e.id for e in self.employees]),
                    ('company', '=', self.company.id),
                    ])
            if employees:
                self.employee = employees[0]

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        res = super(User, cls)._get_preferences(user,
            context_only=context_only)
        if not context_only:
            res['companies'] = [c.id for c in user.companies]
            res['employees'] = [e.id for e in user.employees]
        return res

    @classmethod
    def read(cls, ids, fields_names):
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        result = super(User, cls).read(ids, fields_names)
        if (fields_names
                and ((
                        'company' in fields_names
                        and 'company' in Transaction().context)
                    or ('employee' in fields_names
                        and 'employee' in Transaction().context))):
            values = None
            if int(user_id) in ids:
                for vals in result:
                    if vals['id'] == int(user_id):
                        values = vals
                        break
            if values:
                if ('company' in fields_names
                        and 'company' in Transaction().context):
                    companies = values.get('companies')
                    if not companies:
                        companies = cls.read([user_id],
                            ['companies'])[0]['companies']
                    company_id = Transaction().context['company']
                    if ((company_id and company_id in companies)
                            or not company_id
                            or Transaction().user == 0):
                        values['company'] = company_id
                if ('employee' in fields_names
                        and 'employee' in Transaction().context):
                    employees = values.get('employees')
                    if not employees:
                        employees = cls.read([user_id],
                            ['employees'])[0]['employees']
                    employee_id = Transaction().context['employee']
                    if ((employee_id and employee_id in employees)
                            or not employee_id
                            or Transaction().user == 0):
                        values['employee'] = employee_id
        return result

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Rule = pool.get('ir.rule')
        super(User, cls).write(*args)
        # Restart the cache on the domain_get method
        Rule._domain_get_cache.clear()
