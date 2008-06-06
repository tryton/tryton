"Company"

import copy
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
from trytond.report import Report


class Company(OSV):
    'Company'
    _name = 'company.company'
    _description = __doc__
    _inherits = {'relationship.party': 'party'}

    party = fields.Many2One('relationship.party', 'Party', required=True)
    parent = fields.Many2One('company.company', 'Parent')
    childs = fields.One2Many('company.company', 'parent', 'Childs')
    header = fields.Text('Header')
    footer = fields.Text('Footer')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    employees = fields.One2Many('company.employee', 'company', 'Employees')

    def __init__(self):
        super(Company, self).__init__()
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive companies.', ['parent']),
        ]

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
    _inherits = {'relationship.party': 'party'}

    party = fields.Many2One('relationship.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

Employee()


class User(OSV):
    _name = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
            on_change=['main_company'])
    company = fields.Many2One('company.company', 'Current Company',
            domain="[('parent', 'child_of', [main_company])]")
    employee = fields.Many2One('company.employee', 'Employee',
            domain="[('company', 'child_of', [main_company])]")

    def __init__(self):
        super(User, self).__init__()
        self._context_fields.insert(0, 'company')
        self._constraints += [
                ('check_company',
                    'Error! You can not set a company that is not ' \
                            'a child of your main company.', ['company']),
                ]

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

    def get_preferences(self, cursor, user, context_only=False, context=None):
        res = super(User, self).get_preferences(cursor, user,
                context_only=context_only, context=context)
        if not context_only:
            user = self.browse(cursor, 0, user, context=context)
            res['main_company'] = user.main_company.id
        return res

    def get_preferences_fields_view(self, cursor, user, context=None):
        res = super(User, self).get_preferences_fields_view(cursor, user,
                context=context)
        fields = self.fields_get(cursor, user, fields_names=['main_company'],
                context=context)
        res['fields'].update(fields)
        return res

User()


class Property(OSV):
    _name = 'ir.property'
    company = fields.Many2One('company.company', 'Company')

    def set(self, cursor, user_id, name, model, res_id, val, context=None):
        res = super(Property, self).set(cursor, user_id, name, model, res_id, val,
                context=context)
        if res and user_id:
            user_obj = self.pool.get('res.user')
            user = user_obj.browse(cursor, user_id, user_id, context=context)
            self.write(cursor, user_id, res, {
                'company': user.company.id,
                }, context=context)
        return res

Property()


class CompanyConfigInit(WizardOSV):
    _name = 'company.company.config.init'

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
