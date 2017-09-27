# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.report import Report
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

try:
    import pytz
    TIMEZONES = [(x, x) for x in pytz.common_timezones]
except ImportError:
    TIMEZONES = []
TIMEZONES += [(None, '')]

Transaction.cache_keys.update({'company', 'employee'})

__all__ = ['Company', 'Employee', 'UserEmployee', 'User', 'Property',
    'Sequence', 'SequenceStrict', 'Date', 'CompanyConfigStart',
    'CompanyConfig', 'CompanyReport', 'LetterReport', 'Rule']


class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    parent = fields.Many2One('company.company', 'Parent')
    childs = fields.One2Many('company.company', 'parent', 'Children')
    header = fields.Text('Header')
    footer = fields.Text('Footer')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    timezone = fields.Selection(TIMEZONES, 'Timezone', translate=False)
    employees = fields.One2Many('company.employee', 'company', 'Employees')

    @classmethod
    def __setup__(cls):
        super(Company, cls).__setup__()

    @classmethod
    def validate(cls, companies):
        super(Company, cls).validate(companies)
        cls.check_recursion(companies)

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]

    @classmethod
    def write(cls, companies, values, *args):
        super(Company, cls).write(companies, values, *args)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class Employee(ModelSQL, ModelView):
    'Employee'
    __name__ = 'company.employee'
    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    start_date = fields.Date('Start Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                    ('start_date', '<=', Eval('end_date')),
                    (),
                )
            ],
        depends=['end_date'])
    end_date = fields.Date('End Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                    ('end_date', '>=', Eval('start_date')),
                    (),
                )
            ],
        depends=['start_date'])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]


class UserEmployee(ModelSQL):
    'User - Employee'
    __name__ = 'res.user-company.employee'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True, required=True)


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company')
    company = fields.Many2One('company.company', 'Current Company',
        domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
        depends=['main_company'])
    companies = fields.Function(fields.One2Many('company.company', None,
        'Current Companies'), 'get_companies')
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees')
    employee = fields.Many2One('company.employee', 'Current Employee',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', 'in', Eval('employees', [])),
            ],
        depends=['company', 'employees'])

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
                    company_ids = map(int, Company.search([
                                ('parent', 'child_of', [company.id]),
                                ]))
                    company_childs[company] = company_ids
                if company_ids:
                    companies[user.id].extend(company_ids)
        return companies

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        if self.company:
            status += ' - %s [%s]' % (self.company.rec_name,
                self.company.currency.name)
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
        if user.employee:
            res['employee'] = user.employee.id
            res['employee.rec_name'] = user.employee.rec_name
        if user.company:
            res['company'] = user.company.id
            res['company.rec_name'] = user.company.rec_name
        return res

    @classmethod
    def get_preferences_fields_view(cls):
        pool = Pool()
        Company = pool.get('company.company')

        res = super(User, cls).get_preferences_fields_view()
        res = copy.deepcopy(res)

        def convert2selection(definition, name):
            del definition[name]['relation']
            definition[name]['type'] = 'selection'
            selection = []
            definition[name]['selection'] = selection
            return selection

        if 'company' in res['fields']:
            selection = convert2selection(res['fields'], 'company')
            selection.append((None, ''))
            user = cls(Transaction().user)
            if user.main_company:
                companies = Company.search([
                        ('parent', 'child_of', [user.main_company.id],
                            'parent'),
                        ])
                for company in companies:
                    selection.append((company.id, company.rec_name))
        return res

    @classmethod
    def read(cls, ids, fields_names=None):
        Company = Pool().get('company.company')
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        result = super(User, cls).read(ids, fields_names=fields_names)
        if (fields_names
                and (('company' in fields_names
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
                            or not company_id):
                        values['company'] = company_id
                if ('employee' in fields_names
                        and 'employee' in Transaction().context):
                    employees = values.get('employees')
                    if not employees:
                        employees = cls.read([user_id],
                            ['employees'])[0]['employees']
                    employee_id = Transaction().context['employee']
                    if employee_id and employee_id in employees:
                        values['employee'] = employee_id
        return result

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Rule = pool.get('ir.rule')
        super(User, cls).write(*args)
        # Restart the cache on the domain_get method
        Rule._domain_get_cache.clear()


class Property:
    __metaclass__ = PoolMeta
    __name__ = 'ir.property'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])

    @classmethod
    def _set_values(cls, model, res_id, val, field_id):
        User = Pool().get('res.user')
        user_id = Transaction().user
        if user_id == 0:
            user_id = Transaction().context.get('user', user_id)
        user = User(user_id)
        res = super(Property, cls)._set_values(model, res_id, val, field_id)
        if user and user.company:
            res['company'] = user.company.id
        return res

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        if Transaction().user == 0 and 'user' not in Transaction().context:
            domain = ['AND', domain[:], ('company', '=', None)]
        return super(Property, cls).search(domain, offset=offset, limit=limit,
            order=order, count=count, query=query)


class Sequence:
    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls._order.insert(0, ('company', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class SequenceStrict(Sequence):
    __name__ = 'ir.sequence.strict'


class Date:
    __metaclass__ = PoolMeta
    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if timezone is None and company_id:
            company = Company(company_id)
            if company.timezone:
                timezone = pytz.timezone(company.timezone)
        return super(Date, cls).today(timezone=timezone)


class CompanyConfigStart(ModelView):
    'Company Config'
    __name__ = 'company.company.config.start'


class CompanyConfig(Wizard):
    'Configure Company'
    __name__ = 'company.company.config'
    start = StateView('company.company.config.start',
        'company.company_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'company', 'tryton-ok', True),
            ])
    company = StateView('company.company',
        'company.company_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok', True),
            ])
    add = StateTransition()

    def transition_add(self):
        User = Pool().get('res.user')

        self.company.save()
        users = User.search([
                ('main_company', '=', None),
                ])
        User.write(users, {
                'main_company': self.company.id,
                'company': self.company.id,
                })
        return 'end'


class CompanyReport(Report):

    @classmethod
    def get_context(cls, records, data):
        report_context = super(CompanyReport, cls).get_context(records, data)
        report_context['company'] = report_context['user'].company
        return report_context


class LetterReport(CompanyReport):
    __name__ = 'party.letter'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(LetterReport, cls).execute(ids, data)


class Rule:
    __metaclass__ = PoolMeta
    __name__ = 'ir.rule'

    @classmethod
    def _get_cache_key(cls):
        key = super(Rule, cls)._get_cache_key()
        # XXX Use company from context instead of browse to prevent infinite
        # loop, but the cache is cleared when User is written.
        return key + (Transaction().context.get('company'),
            Transaction().context.get('employee'))
