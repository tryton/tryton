#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Company"

import copy
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
from trytond.report import Report


class Company(OSV):
    'Company'
    _name = 'company.company'
    _description = __doc__
    _inherits = {'party.party': 'party'}

    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    parent = fields.Many2One('company.company', 'Parent')
    childs = fields.One2Many('company.company', 'parent', 'Childs')
    header = fields.Text('Header')
    footer = fields.Text('Footer')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    employees = fields.One2Many('company.employee', 'company', 'Employees')

    def __init__(self):
        super(Company, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_companies'),
        ]
        self._error_messages.update({
            'recursive_companies': 'You can not create recursive companies!',
        })

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Company, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        return res

Company()


class Employee(OSV):
    'Employee'
    _name = 'company.employee'
    _description = __doc__
    _inherits = {'party.party': 'party'}

    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

Employee()


class User(OSV):
    _name = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
            on_change=['main_company'])
    company = fields.Many2One('company.company', 'Current Company',
            domain="[('parent', 'child_of', [main_company], 'parent')]")
    employee = fields.Many2One('company.employee', 'Employee',
            domain="[('company', 'child_of', [main_company], 'parent')]")

    def __init__(self):
        super(User, self).__init__()
        self._context_fields.insert(0, 'company')
        self._constraints += [
                ('check_company', 'child_company'),
                ]
        self._error_messages.update({
            'child_company': 'You can not set a company that is not ' \
                    'a child of your main company!',
        })

    def default_main_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def default_company(self, cursor, user, context=None):
        return self.default_main_company(cursor, user, context=context)

    def get_status_bar(self, cursor, user_id, ids, name, arg, context=None):
        res = super(User, self).get_status_bar(cursor, user_id, ids, name, arg,
                context=context)
        for user in self.browse(cursor, user_id, ids, context=context):
            if user.company:
                res[user.id] += ' ' + user.company.name
        return res

    def on_change_main_company(self, cursor, user, ids, vals, context=None):
        return {'company': vals.get('main_company', False)}

    def check_company(self, cursor, user_id, ids):
        company_obj = self.pool.get('company.company')
        for user in self.browse(cursor, user_id, ids):
            if user.main_company:
                companies = company_obj.search(cursor, user_id, [
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
                if user.company.id and (user.company.id not in companies):
                    return False
            elif user.company:
                return False
        return True

    def get_preferences(self, cursor, user_id, context_only=False, context=None):
        res = super(User, self).get_preferences(cursor, user_id,
                context_only=context_only, context=context)
        user = self.browse(cursor, 0, user_id, context=context)
        if not context_only:
            res['main_company'] = user.main_company.id
        if user.employee:
            res['employee'] = user.employee.id
        return res

    def get_preferences_fields_view(self, cursor, user_id, context=None):
        company_obj = self.pool.get('company.company')

        user = self.browse(cursor, user_id, user_id, context=context)

        res = super(User, self).get_preferences_fields_view(cursor, user_id,
                context=context)
        res = copy.deepcopy(res)

        if 'company' in res['fields']:
            del res['fields']['company']['relation']
            company_ids = company_obj.search(
                    cursor, user_id, [
                        ('parent', 'child_of', [user.main_company.id]),
                    ], context=context)
            res['fields']['company']['selection'] = [
                    (x.id, x.rec_name) for x in company_obj.browse(cursor,
                        user_id, company_ids, context=context)]
        return res

User()


class Property(OSV):
    _name = 'ir.property'
    company = fields.Many2One('company.company', 'Company')

    def set(self, cursor, user_id, name, model, res_id, val, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['user'] = user_id
        res = super(Property, self).set(cursor, user_id, name, model, res_id, val,
                context=context)
        if res and user_id:
            user_obj = self.pool.get('res.user')
            user = user_obj.browse(cursor, user_id, user_id, context=context)
            self.write(cursor, 0, res, {
                'company': user.company.id,
                }, context=ctx)
        return res

Property()


class Sequence(OSV):
    _name = 'ir.sequence'
    company = fields.Many2One('company.company', 'Company',
            domain="[('id', '=', context.get('company', False))]")

    def __init__(self):
        super(Sequence, self).__init__()
        self._order.insert(0, ('company', 'ASC'))

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

Sequence()


class SequenceStrict(Sequence):
    _name = 'ir.sequence.strict'

SequenceStrict()


class CompanyConfigInit(WizardOSV):
    'Company Config Init'
    _name = 'company.company.config.init'
    _description = __doc__

CompanyConfigInit()


class CompanyConfig(Wizard):
    'Configure companies'
    _name = 'company.company.config'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'company.company.config.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('company', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'company': {
            'result': {
                'type': 'form',
                'object': 'company.company',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('add', 'Add', 'tryton-ok', True),
                ],
            },
        },
        'add': {
            'result': {
                'type': 'action',
                'action': '_add',
                'state': 'end',
            },
        },
    }

    def _add(self, cursor, user, data, context=None):
        company_obj = self.pool.get('company.company')
        user_obj = self.pool.get('res.user')

        company_id = company_obj.create(cursor, user, data['form'],
                context=context)
        user_ids = user_obj.search(cursor, user, [
            ('main_company', '=', False),
            ], context=context)
        user_obj.write(cursor, user, user_ids, {
            'main_company': company_id,
            'company': company_id,
            }, context=context)
        return {}

CompanyConfig()


class CompanyReport(Report):

    def parse(self, cursor, user_id, report, objects, datas, context):
        user_obj = self.pool.get('res.user')

        user = user_obj.browse(cursor, user_id, user_id, context)
        if context is None:
            context = {}
        context = context.copy()
        context['company'] = user.company

        return super(CompanyReport, self).parse(cursor, user_id, report,
                objects, datas, context)

import trytond.report
trytond.report.CompanyReport = CompanyReport


class LetterReport(CompanyReport):
    _name = 'party.letter'

    def parse(self, cursor, user_id, report, objects, datas, context):
        user_obj = self.pool.get('res.user')

        user = user_obj.browse(cursor, user_id, user_id, context)
        if context is None:
            context = {}
        context = context.copy()
        context['user'] = user

        return super(LetterReport, self).parse(cursor, user_id, report,
                objects, datas, context)

LetterReport()
