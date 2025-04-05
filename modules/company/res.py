# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.cache import Cache
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class UserCompany(ModelSQL):
    __name__ = 'res.user-company.company'

    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE', required=True)
    company = fields.Many2One(
        'company.company', "Company",
        ondelete='CASCADE', required=True)

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        User = pool.get('res.user')
        super().on_modification(mode, records, field_names=field_names)
        User._get_companies_cache.clear()


class UserEmployee(ModelSQL):
    __name__ = 'res.user-company.employee'
    user = fields.Many2One(
        'res.user', "User", ondelete='CASCADE', required=True)
    employee = fields.Many2One(
        'company.employee', "Employee", ondelete='CASCADE', required=True)

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        User = pool.get('res.user')
        super().on_modification(mode, records, field_names=field_names)
        User._get_employees_cache.clear()


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
        states={
            'invisible': ~Eval('companies', []),
            },
        help="Select the company to work for.")
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees',
        domain=[
            ('company', 'in', Eval('companies', [])),
            ],
        help="Add employees to grant the user access to them.")
    employee = fields.Many2One('company.employee', 'Current Employee',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', 'in', Eval('employees', [])),
            ],
        states={
            'invisible': ~Eval('employees', []),
            },
        help="Select the employee to make the user behave as such.")
    company_filter = fields.Selection([
            ('one', "Current"),
            ('all', "All"),
            ], "Company Filter",
        states={
            'invisible': ~Eval('companies', []),
            },
        help="Define records of which companies are shown.")
    _get_companies_cache = Cache(__name__ + '.get_companies', context=False)
    _get_employees_cache = Cache(__name__ + '.get_employees', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._context_fields.insert(0, 'company')
        cls._context_fields.insert(0, 'employee')
        cls._context_fields.insert(0, 'company_filter')

    @classmethod
    def default_companies(cls):
        pool = Pool()
        Company = pool.get('company.company')
        companies = Company.search([])
        if len(companies) == 1:
            return [c.id for c in companies]

    @classmethod
    def default_company(cls):
        if companies := cls.default_companies():
            if len(companies) == 1:
                return companies[0]

    @classmethod
    def default_company_filter(cls):
        return 'one'

    def get_status_bar(self, name):
        def same_company(record):
            return record.company == self.company
        status = super().get_status_bar(name)
        if (self.employee
                and len(list(filter(same_company, self.employees))) > 1):
            status += ' - %s' % self.employee.rec_name
        if self.company:
            if len(self.companies) > 1:
                status += ' - %s' % self.company.rec_name
            status += ' [%s]' % self.company.currency.code
        return status

    @fields.depends(
        'companies', 'company', 'employees', methods=['on_change_employees'])
    def on_change_companies(self):
        companies = set(self.companies or [])
        if self.company and self.company not in companies:
            self.company = None
        if self.employees:
            employees = []
            for employee in self.employees:
                if employee.company in companies:
                    employees.append(employee)
            self.employees = employees
            self.on_change_employees()

    @fields.depends('employees', 'employee')
    def on_change_employees(self):
        employees = set(self.employees or [])
        if self.employee and self.employee not in employees:
            self.employee = None

    @fields.depends('company', 'employees', 'employee')
    def on_change_company(self):
        if self.employee and self.employee.company != self.company:
            self.employee = None
        employees = [
            e for e in (self.employees or []) if e.company == self.company]
        if len(employees) == 1:
            self.employee, = employees

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        res = super()._get_preferences(user,
            context_only=context_only)
        if not context_only:
            res['companies'] = [c.id for c in user.companies]
            res['employees'] = [e.id for e in user.employees]
        return res

    @classmethod
    def get_companies(cls):
        '''
        Return an ordered tuple of company ids for the user
        '''
        transaction = Transaction()
        user_id = transaction.user
        companies = cls._get_companies_cache.get(user_id)
        if companies is not None:
            return companies
        user = cls(user_id)
        if user.company_filter == 'one':
            companies = [user.company.id] if user.company else []
        elif user.company_filter == 'all':
            companies = [c.id for c in user.companies]
        else:
            companies = []
        companies = tuple(companies)
        cls._get_companies_cache.set(user_id, companies)
        return companies

    @classmethod
    def get_employees(cls):
        '''
        Return an ordered tuple of employee ids for the user
        '''
        transaction = Transaction()
        user_id = transaction.user
        employees = cls._get_employees_cache.get(user_id)
        if employees is not None:
            return employees
        user = cls(user_id)
        if user.company_filter == 'one':
            employees = [user.employee.id] if user.employee else []
        elif user.company_filter == 'all':
            employees = [e.id for e in user.employees]
        else:
            employees = []
        employees = tuple(employees)
        cls._get_employees_cache.set(user_id, employees)
        return employees

    @classmethod
    def read(cls, ids, fields_names):
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        result = super().read(ids, fields_names)
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
                    else:
                        values['company'] = None
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
                    else:
                        values['employee'] = None
        return result

    @classmethod
    def on_modification(cls, mode, users, field_names=None):
        super().on_modification(mode, users, field_names=field_names)
        if mode == 'write':
            cls._get_companies_cache.clear()
            cls._get_employees_cache.clear()
