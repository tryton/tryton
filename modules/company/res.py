# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class UserEmployee(ModelSQL):
    'User - Employee'
    __name__ = 'res.user-company.employee'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True, required=True)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
        help="Grant access to the company and its children.")
    company = fields.Many2One('company.company', 'Current Company',
        domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
        depends=['main_company'],
        help="Select the company to work for.")
    companies = fields.Function(fields.One2Many('company.company', None,
            'Companies'), 'get_companies')
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees',
        help="Add employees to grant the user access to them.")
    employee = fields.Many2One('company.employee', 'Current Employee',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', 'in', Eval('employees', [])),
            ],
        depends=['company', 'employees'],
        help="Select the employee to make the user behave as such.")

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.insert(0, 'company')
        cls._context_fields.insert(0, 'employee')

    @staticmethod
    def default_main_company():
        return Transaction().context.get('company')

    @classmethod
    def default_company(cls):
        return cls.default_main_company()

    @classmethod
    def get_companies(cls, users, name):
        Company = Pool().get('company.company')
        companies = {}
        company_childs = {}
        for user in users:
            companies[user.id] = []
            company = None
            if user.company:
                company = user.company
            elif user.main_company:
                company = user.main_company
            if company:
                if company in company_childs:
                    company_ids = company_childs[company]
                else:
                    company_ids = list(map(int, Company.search([
                                ('parent', 'child_of', [company.id]),
                                ])))
                    company_childs[company] = company_ids
                if company_ids:
                    companies[user.id].extend(company_ids)
        return companies

    def get_status_bar(self, name):
        def same_company(record):
            return record.company == self.company
        status = super(User, self).get_status_bar(name)
        if (self.employee
                and len(list(filter(same_company, self.employees))) > 1):
            status += ' - %s' % self.employee.rec_name
        if self.company:
            if self.main_company.childs:
                status += ' - %s' % self.company.rec_name
            status += ' [%s]' % self.company.currency.code
        return status

    @fields.depends('main_company')
    def on_change_main_company(self):
        self.company = self.main_company
        self.employee = None

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
            res['main_company'] = None
            if user.main_company:
                res['main_company'] = user.main_company.id
                res['main_company.rec_name'] = user.main_company.rec_name
            res['employees'] = [e.id for e in user.employees]
        return res

    @classmethod
    def read(cls, ids, fields_names):
        Company = Pool().get('company.company')
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
                    main_company_id = values.get('main_company')
                    if not main_company_id:
                        main_company_id = cls.read([user_id],
                            ['main_company'])[0]['main_company']
                    companies = Company.search([
                            ('parent', 'child_of', [main_company_id]),
                            ])
                    company_id = Transaction().context['company']
                    if ((company_id and company_id in map(int, companies))
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
