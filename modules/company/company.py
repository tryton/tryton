#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.report import Report
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Company', 'Employee', 'UserEmployee', 'User', 'Property',
    'Sequence', 'SequenceStrict', 'CompanyConfigStart', 'CompanyConfig',
    'CompanyReport', 'LetterReport']
__metaclass__ = PoolMeta


class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'
    _rec_name = 'party'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    parent = fields.Many2One('company.company', 'Parent')
    childs = fields.One2Many('company.company', 'parent', 'Children')
    header = fields.Text('Header')
    footer = fields.Text('Footer')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
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
    def write(cls, companies, vals):
        super(Company, cls).write(companies, vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class Employee(ModelSQL, ModelView):
    'Employee'
    __name__ = 'company.employee'
    _rec_name = 'party'
    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    def get_rec_name(self, name):
        return self.party.rec_name


class UserEmployee(ModelSQL):
    'User - Employee'
    __name__ = 'res.user-company.employee'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True, required=True)


class User:
    __name__ = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
        on_change=['main_company'])
    company = fields.Many2One('company.company', 'Current Company',
        domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
        depends=['main_company'], on_change=['company', 'employees'])
    companies = fields.Function(fields.One2Many('company.company', None,
        'Current Companies'), 'get_companies')
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees')
    employee = fields.Many2One('company.employee', 'Current Employee',
        domain=[
            ('company', '=', Eval('company')),
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

    def on_change_main_company(self):
        return {
            'company': self.main_company.id if self.main_company else None,
            'employee': None,
            }

    def on_change_company(self):
        Employee = Pool().get('company.employee')
        result = {
            'employee': None,
            }
        if self.company and self.employees:
            employees = Employee.search([
                    ('id', 'in', [e.id for e in self.employees]),
                    ('company', '=', self.company.id),
                    ])
            if employees:
                result['employee'] = employees[0].id
        return result

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
            res['employee'] = None
            if user.employee:
                res['employee'] = user.employee.id
                res['employee.rec_name'] = user.employee.rec_name
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
                and 'company' in fields_names
                and 'company' in Transaction().context):
            values = None
            if int(user_id) in ids:
                for vals in result:
                    if vals['id'] == int(user_id):
                        values = vals
                        break
            if values:
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
        return result


class Property:
    __name__ = 'ir.property'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
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
            query_string=False):
        if Transaction().user == 0 and not 'user' in Transaction().context:
            domain = ['AND', domain[:], ('company', '=', None)]
        return super(Property, cls).search(domain, offset=offset, limit=limit,
            order=order, count=count, query_string=query_string)


class Sequence:
    __name__ = 'ir.sequence'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
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


class CompanyConfigStart(ModelView):
    'Company Config'
    __name__ = 'company.company.config.start'


class CompanyConfig(Wizard):
    'Configure Company'
    __name__ = 'company.company.config'
    start = StateView('company.company.config.start',
        'company.company_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'company', 'tryton-ok', True),
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
    def parse(cls, report, records, data, localcontext):
        user = Pool().get('res.user')(Transaction().user)
        localcontext['company'] = user.company
        return super(CompanyReport, cls).parse(report, records, data,
            localcontext)


class LetterReport(CompanyReport):
    __name__ = 'party.letter'
